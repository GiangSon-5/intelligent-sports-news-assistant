"""
AI Engine Module — orchestrator.py
LangChain orchestration với Gemini (primary) + OpenAI (fallback).
Implements: summarization, keyword extraction, highlighted news selection.
Full edge case handling theo SPEC §6 (10 edge cases).
"""

import json
import time
from datetime import datetime, timezone, timedelta

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ai_engine.prompts import (
    BATCH_SUMMARY_PROMPT,
    EXECUTIVE_SUMMARY_PROMPT,
    HIGHLIGHTED_NEWS_PROMPT,
    KEYWORD_EXTRACTION_PROMPT,
)
from logger import get_logger, log_function

_log = get_logger("ai_engine")
_VN_TZ = timezone(timedelta(hours=7))


class AIProcessingError(Exception):
    """AI processing error — both Gemini and OpenAI failed (Edge Case #3)."""
    pass


class AIOrchestrator:
    """
    Central AI orchestrator — LangChain with Gemini primary + OpenAI fallback.
    3 tasks: Executive Summary, Keyword Extraction, Highlighted News.
    """

    def __init__(self, settings):
        self.settings = settings
        self._fallback_triggered = False
        self._model_used = settings.PRIMARY_MODEL
        self._total_tokens = 0

        self.llm = self._build_llm_with_fallback()

        _log.info(
            f"AIOrchestrator initialized | primary={settings.PRIMARY_MODEL} | "
            f"fallback={'enabled: ' + settings.FALLBACK_MODEL if settings.ENABLE_FALLBACK else 'disabled'}"
        )

    # ------------------------------------------------------------------
    #  LLM Builder with Fallback (SPEC §3.1)
    # ------------------------------------------------------------------

    def _build_llm_with_fallback(self):
        """Build LLM chain: Gemini (primary) → Gemini Cascade → OpenAI (fallback)."""
        start = time.perf_counter()

        primary = ChatGoogleGenerativeAI(
            model=self.settings.PRIMARY_MODEL,
            google_api_key=self.settings.GEMINI_API_KEY,
            temperature=0.3,
            max_output_tokens=self.settings.SUMMARY_MAX_TOKENS,
            timeout=self.settings.API_TIMEOUT_SECONDS,
        )

        fallbacks = []

        # 1. Gemini Cascade Fallbacks
        for fallback_model_name in self.settings.get_gemini_fallbacks():
            fallbacks.append(
                ChatGoogleGenerativeAI(
                    model=fallback_model_name,
                    google_api_key=self.settings.GEMINI_API_KEY,
                    temperature=0.3,
                    max_output_tokens=self.settings.SUMMARY_MAX_TOKENS,
                    timeout=self.settings.API_TIMEOUT_SECONDS,
                )
            )

        # 2. OpenAI Final Fallback
        if self.settings.ENABLE_FALLBACK and self.settings.OPENAI_API_KEY:
            fallbacks.append(
                ChatOpenAI(
                    model=self.settings.FALLBACK_MODEL,
                    api_key=self.settings.OPENAI_API_KEY,
                    temperature=0.3,
                    max_tokens=self.settings.SUMMARY_MAX_TOKENS,
                    timeout=self.settings.API_TIMEOUT_SECONDS,
                )
            )

        if fallbacks:
            combined = primary.with_fallbacks(fallbacks)
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            # Debug names
            fb_names = [f"gemini:{m.model}" if hasattr(m, "model") else "openai" for m in fallbacks]
            _log.info(f"LLM chain built with fallbacks: {fb_names} | latency={elapsed}ms")
            return combined

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"LLM chain built (primary only, no fallback) | latency={elapsed}ms")
        return primary

    # ------------------------------------------------------------------
    #  Main Process Entry Point
    # ------------------------------------------------------------------

    @log_function("ai_engine")
    def process(self, articles: list[dict], analysis: dict) -> dict:
        """
        Main entry point — run all 3 AI tasks and compile result.
        Output matches SPEC §2.2 schema.
        """
        start = time.perf_counter()

        # Edge Case #8: Input 0 articles
        if not articles:
            _log.warning("process() called with 0 articles — returning default output")
            return {
                "executive_summary": "No sports news data for this week to analyze.",
                "trending_keywords": [],
                "highlighted_news": [],
                "model_used": self.settings.PRIMARY_MODEL,
                "fallback_triggered": False,
                "processing_timestamp": datetime.now(_VN_TZ).isoformat(),
                "total_tokens_used": 0,
            }

        # Limit articles (SPEC config)
        max_articles = self.settings.MAX_ARTICLES_PER_SUMMARY
        if len(articles) > max_articles:
            _log.info(f"Limiting articles from {len(articles)} to {max_articles}")
            articles = articles[:max_articles]

        # Task 1: Executive Summary
        _log.info("Task 1/3: Generating Executive Summary...")
        executive_summary = self._safe_generate_executive_summary(articles, analysis)

        # Task 2: Keyword Extraction
        _log.info("Task 2/3: Extracting trending keywords...")
        trending_keywords = self._safe_extract_keywords(articles)

        # Task 3: Highlighted News
        _log.info("Task 3/3: Selecting highlighted news...")
        highlighted_news = self._safe_select_highlighted_news(articles)

        # Compile result (SPEC §2.2 schema)
        result = {
            "executive_summary": executive_summary,
            "trending_keywords": trending_keywords,
            "highlighted_news": highlighted_news,
            "model_used": self._model_used,
            "fallback_triggered": self._fallback_triggered,
            "processing_timestamp": datetime.now(_VN_TZ).isoformat(),
            "total_tokens_used": self._total_tokens,
        }

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"AI processing complete | model={self._model_used} | "
            f"fallback={self._fallback_triggered} | latency={elapsed}ms"
        )

        return result

    # ------------------------------------------------------------------
    #  Task 1: Executive Summary (SPEC §3.2)
    # ------------------------------------------------------------------

    def _safe_generate_executive_summary(self, articles: list[dict], analysis: dict) -> str:
        """Wrapper with retry and error handling."""
        try:
            return self._generate_executive_summary(articles, analysis)
        except Exception as e:
            _log.error(f"Executive Summary generation failed: {e}")
            return (
                f"Cannot create Executive Summary due to AI error: {type(e).__name__}. "
                f"Total of {analysis.get('total_articles', 0)} articles have been collected "
                f"from {', '.join(analysis.get('source_list', []))}."
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True,
    )
    def _generate_executive_summary(self, articles: list[dict], analysis: dict) -> str:
        """Generate Executive Summary via batch summarize + final compilation."""
        start = time.perf_counter()

        # Batch summarize (SPEC §3.5)
        article_summaries = self._batch_summarize(articles)

        # Final Executive Summary
        prompt = ChatPromptTemplate.from_template(EXECUTIVE_SUMMARY_PROMPT)
        chain = prompt | self.llm | StrOutputParser()

        result = self._invoke_with_retry(chain, {
            "article_summaries": article_summaries,
            "total_articles": analysis.get("total_articles", len(articles)),
            "date_from": analysis.get("date_range", {}).get("from", "N/A"),
            "date_to": analysis.get("date_range", {}).get("to", "N/A"),
            "sources": ", ".join(analysis.get("source_list", [])),
        })

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"Executive Summary generated | length={len(result)} chars | latency={elapsed}ms")

        return result.strip()

    # ------------------------------------------------------------------
    #  Task 2: Keyword Extraction (SPEC §3.3)
    # ------------------------------------------------------------------

    def _safe_extract_keywords(self, articles: list[dict]) -> list[dict]:
        """Wrapper with retry and error handling."""
        try:
            return self._extract_trending_keywords(articles)
        except Exception as e:
            _log.error(f"Keyword extraction failed: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True,
    )
    def _extract_trending_keywords(self, articles: list[dict]) -> list[dict]:
        """Extract trending keywords from article corpus."""
        start = time.perf_counter()

        text_corpus = self._prepare_text_corpus(articles)

        prompt = ChatPromptTemplate.from_template(KEYWORD_EXTRACTION_PROMPT)
        chain = prompt | self.llm | JsonOutputParser()

        result = self._invoke_with_retry(chain, {
            "text_corpus": text_corpus,
            "num_keywords": self.settings.KEYWORD_EXTRACTION_COUNT,
        })

        # Extract keywords list from response
        keywords = result.get("keywords", result) if isinstance(result, dict) else result
        if not isinstance(keywords, list):
            keywords = []

        # Edge Case #9: Deduplicate keywords
        keywords = self._deduplicate_keywords(keywords)

        # Validate categories
        valid_categories = {
            "football", "basketball", "tennis", "esports",
            "swimming", "athletics", "multi-sport", "other",
        }
        for kw in keywords:
            if kw.get("category", "other") not in valid_categories:
                kw["category"] = "other"

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"Keywords extracted: {len(keywords)} | latency={elapsed}ms")

        return keywords

    # ------------------------------------------------------------------
    #  Task 3: Highlighted News (SPEC §3.4)
    # ------------------------------------------------------------------

    def _safe_select_highlighted_news(self, articles: list[dict]) -> list[dict]:
        """Wrapper with retry and error handling."""
        try:
            return self._select_highlighted_news(articles)
        except Exception as e:
            _log.error(f"Highlighted news selection failed: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True,
    )
    def _select_highlighted_news(self, articles: list[dict]) -> list[dict]:
        """Select top N highlighted news articles."""
        start = time.perf_counter()

        # Prepare article briefs
        article_briefs = []
        for a in articles:
            brief = {
                "title": a.get("title", ""),
                "content_preview": a.get("content", "")[:300],
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "publish_date": a.get("publish_date", a.get("publish_date_dt", "")),
            }
            article_briefs.append(brief)

        prompt = ChatPromptTemplate.from_template(HIGHLIGHTED_NEWS_PROMPT)
        chain = prompt | self.llm | JsonOutputParser()

        result = self._invoke_with_retry(chain, {
            "articles": json.dumps(article_briefs, ensure_ascii=False),
            "top_n": self.settings.TOP_HIGHLIGHTED_NEWS,
        })

        highlighted = result.get("highlighted_news", result) if isinstance(result, dict) else result
        if not isinstance(highlighted, list):
            highlighted = []

        # Edge Case #10: Validate URLs against input articles
        valid_urls = {a.get("url", "") for a in articles}
        validated = []
        for news in highlighted:
            url = news.get("url", "")
            if url in valid_urls:
                validated.append(news)
            else:
                _log.warning(f"Hallucinated URL removed: {url}")
                # Try to find closest match by title
                title = news.get("title", "")
                for a in articles:
                    if a.get("title", "") == title:
                        news["url"] = a["url"]
                        news["source"] = a.get("source", news.get("source", ""))
                        validated.append(news)
                        break

        # Sort by relevance_score descending
        validated.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"Highlighted news selected: {len(validated)} | latency={elapsed}ms")

        return validated

    # ------------------------------------------------------------------
    #  Batch Summarize (SPEC §3.5)
    # ------------------------------------------------------------------

    def _batch_summarize(self, articles: list[dict], batch_size: int = 100) -> str:
        """
        Split articles into batches → summarize each batch → merge.
        Optimized for Gemini 2.5 Flash: large batch_size (protect 20 RPD).
        """
        start = time.perf_counter()
        summaries = []
        total_batches = (len(articles) + batch_size - 1) // batch_size

        for i in range(0, len(articles), batch_size):
            batch_num = (i // batch_size) + 1
            batch = articles[i:i + batch_size]

            batch_text = "\n\n".join([
                f"**{a.get('title', 'N/A')}** ({a.get('source', 'N/A')}, {a.get('publish_date', a.get('publish_date_dt', 'N/A'))})\n{a.get('content', '')[:500]}"
                for a in batch
            ])

            try:
                prompt = ChatPromptTemplate.from_template(BATCH_SUMMARY_PROMPT)
                chain = prompt | self.llm | StrOutputParser()
                summary = self._invoke_with_retry(chain, {"articles": batch_text})
                summaries.append(summary.strip())
                _log.debug(f"Batch {batch_num}/{total_batches} summarized | chars={len(summary)}")
                
                # Anti-Rate-Limit: Wait to respect 5 RPM Gemini 2.5 Flash Free Tier
                if batch_num < total_batches:
                    time.sleep(15)
                    
            except Exception as e:
                _log.warning(f"Batch {batch_num}/{total_batches} summarization failed: {e}")
                self._fallback_triggered = True
                # Fallback: use titles as summary
                titles = "; ".join(a.get("title", "") for a in batch)
                summaries.append(f"Key articles: {titles}")

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"Batch summarization complete: {total_batches} batches | latency={elapsed}ms")

        return "\n\n".join(summaries)

    # ------------------------------------------------------------------
    #  Helper Methods
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        reraise=True,
    )
    def _invoke_with_retry(self, chain, params):
        """Helper to call LLM with stronger Rate Limit (429) protection."""
        return chain.invoke(params)

    def _prepare_text_corpus(self, articles: list[dict]) -> str:
        """Concat titles + first 200 chars of content for keyword extraction."""
        parts = []
        for a in articles:
            title = a.get("title", "")
            content_preview = a.get("content", "")[:200]
            parts.append(f"{title}. {content_preview}")

        corpus = "\n".join(parts)

        # Limit corpus size (~50K chars max)
        if len(corpus) > 50000:
            corpus = corpus[:50000]
            _log.info("Text corpus truncated to 50K chars")

        return corpus

    @staticmethod
    def _deduplicate_keywords(keywords: list[dict]) -> list[dict]:
        """Edge Case #9: Dedup keywords by name, merge frequency."""
        seen = {}
        for kw in keywords:
            name = kw.get("keyword", "").strip().lower()
            if name in seen:
                # Merge: keep higher frequency
                if kw.get("frequency", 0) > seen[name].get("frequency", 0):
                    seen[name] = kw
            else:
                seen[name] = kw

        return list(seen.values())
