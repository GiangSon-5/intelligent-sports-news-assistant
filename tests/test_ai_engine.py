"""
Tests — test_ai_engine.py
Unit tests for AI Engine module (orchestrator.py, prompts.py).
Covers: mock LLM calls, edge cases, output schema validation.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

_VN_TZ = timezone(timedelta(hours=7))


@pytest.fixture
def mock_settings():
    """Mock AppSettings."""
    settings = MagicMock()
    settings.GEMINI_API_KEY = "AIzaSyTestKey"
    settings.OPENAI_API_KEY = "sk-testkey"
    settings.PRIMARY_MODEL = "gemini-2.0-flash"
    settings.FALLBACK_MODEL = "gpt-4o"
    settings.ENABLE_FALLBACK = True
    settings.SUMMARY_MAX_TOKENS = 1024
    settings.API_TIMEOUT_SECONDS = 30
    settings.MAX_ARTICLES_PER_SUMMARY = 50
    settings.KEYWORD_EXTRACTION_COUNT = 15
    settings.TOP_HIGHLIGHTED_NEWS = 10
    return settings


@pytest.fixture
def sample_articles():
    """Sample processed articles."""
    now = datetime.now(_VN_TZ)
    return [
        {
            "title": "Đội tuyển Việt Nam thắng Thái Lan 2-1",
            "content": "Trong trận đấu căng thẳng tối ngày 14/4 tại sân Mỹ Đình " * 10,
            "source": "vnexpress",
            "url": "https://vnexpress.net/test-1.html",
            "publish_date": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
            "publish_date_dt": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
        },
        {
            "title": "Hoàng Đức giành Quả bóng Vàng 2026",
            "content": "Tiền vệ Hoàng Đức trở thành cầu thủ đầu tiên " * 10,
            "source": "thanhnien",
            "url": "https://thanhnien.vn/test-2.htm",
            "publish_date": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
            "publish_date_dt": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
        },
    ]


@pytest.fixture
def sample_analysis():
    """Sample analysis result."""
    now = datetime.now(_VN_TZ)
    return {
        "total_articles": 2,
        "articles_per_source": {"vnexpress": 1, "thanhnien": 1},
        "articles_per_day": {(now - timedelta(days=2)).strftime("%Y-%m-%d"): 1},
        "avg_content_length": 450,
        "avg_word_count": 80,
        "date_range": {
            "from": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
            "to": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        },
        "source_list": ["vnexpress", "thanhnien"],
    }


# ---------------------------------------------------------------------------
#  Test Prompts
# ---------------------------------------------------------------------------

class TestPrompts:
    """Test prompt templates."""

    def test_executive_summary_prompt_has_placeholders(self):
        """Prompt contains {date_from}, {date_to}, {total_articles}, {sources}, {article_summaries}."""
        from ai_engine.prompts import EXECUTIVE_SUMMARY_PROMPT
        assert "{date_from}" in EXECUTIVE_SUMMARY_PROMPT
        assert "{date_to}" in EXECUTIVE_SUMMARY_PROMPT
        assert "{total_articles}" in EXECUTIVE_SUMMARY_PROMPT
        assert "{sources}" in EXECUTIVE_SUMMARY_PROMPT
        assert "{article_summaries}" in EXECUTIVE_SUMMARY_PROMPT

    def test_keyword_prompt_has_placeholders(self):
        """Prompt contains {num_keywords}, {text_corpus}."""
        from ai_engine.prompts import KEYWORD_EXTRACTION_PROMPT
        assert "{num_keywords}" in KEYWORD_EXTRACTION_PROMPT
        assert "{text_corpus}" in KEYWORD_EXTRACTION_PROMPT

    def test_highlighted_prompt_has_placeholders(self):
        """Prompt contains {top_n}, {articles}."""
        from ai_engine.prompts import HIGHLIGHTED_NEWS_PROMPT
        assert "{top_n}" in HIGHLIGHTED_NEWS_PROMPT
        assert "{articles}" in HIGHLIGHTED_NEWS_PROMPT

    def test_batch_prompt_has_placeholder(self):
        """Prompt contains {articles}."""
        from ai_engine.prompts import BATCH_SUMMARY_PROMPT
        assert "{articles}" in BATCH_SUMMARY_PROMPT


# ---------------------------------------------------------------------------
#  Test AIOrchestrator
# ---------------------------------------------------------------------------

class TestAIOrchestrator:
    """Test AIOrchestrator with mocked LLM."""

    @patch("ai_engine.orchestrator.ChatGoogleGenerativeAI")
    @patch("ai_engine.orchestrator.ChatOpenAI")
    def test_init_builds_llm_with_fallback(self, mock_openai, mock_gemini, mock_settings):
        """Init builds Gemini primary + OpenAI fallback."""
        mock_gemini_instance = MagicMock()
        mock_gemini.return_value = mock_gemini_instance
        mock_gemini_instance.with_fallbacks.return_value = MagicMock()

        from ai_engine.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator(mock_settings)
        assert orchestrator.llm is not None
        mock_gemini_instance.with_fallbacks.assert_called_once()

    @patch("ai_engine.orchestrator.ChatGoogleGenerativeAI")
    def test_init_no_fallback(self, mock_gemini, mock_settings):
        """Fallback disabled → only Gemini primary."""
        mock_settings.ENABLE_FALLBACK = False
        mock_gemini_instance = MagicMock()
        mock_gemini.return_value = mock_gemini_instance

        from ai_engine.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator(mock_settings)
        assert orchestrator.llm is not None
        mock_gemini_instance.with_fallbacks.assert_not_called()

    @patch("ai_engine.orchestrator.ChatGoogleGenerativeAI")
    @patch("ai_engine.orchestrator.ChatOpenAI")
    def test_process_empty_articles(self, mock_openai, mock_gemini, mock_settings, sample_analysis):
        """Edge Case #8: 0 articles → default output."""
        mock_gemini.return_value = MagicMock()
        mock_gemini.return_value.with_fallbacks.return_value = MagicMock()

        from ai_engine.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator(mock_settings)
        result = orchestrator.process(articles=[], analysis=sample_analysis)

        assert result["executive_summary"] == "No sports news data for this week to analyze."
        assert result["trending_keywords"] == []
        assert result["highlighted_news"] == []
        assert result["model_used"] == "gemini-2.0-flash"
        assert result["fallback_triggered"] is False

    @patch("ai_engine.orchestrator.ChatGoogleGenerativeAI")
    @patch("ai_engine.orchestrator.ChatOpenAI")
    def test_process_output_schema(self, mock_openai, mock_gemini, mock_settings, sample_articles, sample_analysis):
        """Output matching SPEC §2.2 schema."""
        mock_llm = MagicMock()
        mock_gemini.return_value = mock_llm
        mock_llm.with_fallbacks.return_value = mock_llm
        # Mock the chain invocations
        mock_llm.__or__ = MagicMock(return_value=mock_llm)

        from ai_engine.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator(mock_settings)

        # Mock individual methods
        orchestrator._safe_generate_executive_summary = MagicMock(return_value="Test summary")
        orchestrator._safe_extract_keywords = MagicMock(return_value=[
            {"keyword": "AFF Cup", "frequency": 45, "category": "football"}
        ])
        orchestrator._safe_select_highlighted_news = MagicMock(return_value=[
            {"title": "Test", "summary": "Test summary", "url": "https://test.com", "source": "vnexpress", "relevance_score": 0.95}
        ])

        result = orchestrator.process(articles=sample_articles, analysis=sample_analysis)

        # Validate output schema
        assert "executive_summary" in result
        assert "trending_keywords" in result
        assert "highlighted_news" in result
        assert "model_used" in result
        assert "fallback_triggered" in result
        assert "processing_timestamp" in result
        assert "total_tokens_used" in result

    def test_prepare_text_corpus(self, mock_settings, sample_articles):
        """_prepare_text_corpus: concat titles + content preview."""
        with patch("ai_engine.orchestrator.ChatGoogleGenerativeAI"), \
             patch("ai_engine.orchestrator.ChatOpenAI"):
            from ai_engine.orchestrator import AIOrchestrator
            orchestrator = AIOrchestrator(mock_settings)
            corpus = orchestrator._prepare_text_corpus(sample_articles)
            assert "Đội tuyển Việt Nam" in corpus
            assert "Hoàng Đức" in corpus

    def test_deduplicate_keywords(self):
        """Edge Case #9: Duplicate keywords → merge."""
        from ai_engine.orchestrator import AIOrchestrator
        keywords = [
            {"keyword": "AFF Cup", "frequency": 45, "category": "football"},
            {"keyword": "aff cup", "frequency": 30, "category": "football"},
            {"keyword": "V-League", "frequency": 20, "category": "football"},
        ]
        result = AIOrchestrator._deduplicate_keywords(keywords)
        # "AFF Cup" and "aff cup" → merged into 1
        names = [kw["keyword"].lower() for kw in result]
        assert names.count("aff cup") == 1
        assert len(result) == 2
