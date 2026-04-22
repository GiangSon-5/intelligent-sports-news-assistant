"""
A/B Testing — experiment.py
Core engine: chạy A/B experiment, thu thập metrics, lưu kết quả.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from logger import get_logger

_log = get_logger("ab_testing")
_VN_TZ = timezone(timedelta(hours=7))


@dataclass
class ExperimentResult:
    """Kết quả của 1 lần chạy experiment."""

    experiment_name: str
    variant_a_name: str
    variant_b_name: str
    variant_a_output: str = ""
    variant_b_output: str = ""
    variant_a_latency_ms: float = 0.0
    variant_b_latency_ms: float = 0.0
    variant_a_score: float = 0.0
    variant_b_score: float = 0.0
    winner: str = ""
    margin: float = 0.0
    verdict: str = ""
    timestamp: str = ""
    input_summary: str = ""          # Mô tả input đã dùng
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ABExperiment:
    """
    A/B Testing Engine — chạy 2 variants trên cùng input, so sánh kết quả.

    Hỗ trợ 3 loại experiment:
    1. Prompt A/B: Cùng model, khác prompt
    2. Model A/B: Cùng prompt, khác model
    3. Parameter A/B: Cùng model+prompt, khác temperature/max_tokens

    Usage:
        from tests.ab_testing import ABExperiment
        from tests.ab_testing.variants import PROMPT_SUMMARY_CONCISE, PROMPT_SUMMARY_DETAILED

        exp = ABExperiment(
            name="summary_length_test",
            settings=get_settings(),
        )

        result = exp.run_prompt_ab(
            variant_a=PROMPT_SUMMARY_CONCISE,
            variant_b=PROMPT_SUMMARY_DETAILED,
            input_data={"article_summaries": "...", ...},
        )

        print(f"Winner: {result.winner} (margin: {result.margin})")
    """

    def __init__(self, name: str, settings, results_dir: str = "storage/ab_results"):
        self.name = name
        self.settings = settings
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[ExperimentResult] = []

        _log.info(f"ABExperiment '{name}' initialized | results_dir={results_dir}")

    # ------------------------------------------------------------------
    #  Experiment Type 1: Prompt A/B (Cùng model, khác prompt)
    # ------------------------------------------------------------------

    def run_prompt_ab(
        self,
        variant_a,  # PromptVariant
        variant_b,  # PromptVariant
        input_data: dict,
        output_parser: str = "str",  # "str" | "json"
        target_word_range: tuple[int, int] = (200, 400),
    ) -> ExperimentResult:
        """
        Chạy 2 prompt variants trên cùng 1 model, so sánh output.

        Args:
            variant_a, variant_b: PromptVariant objects
            input_data: dict template variables cho prompt
            output_parser: "str" (text) hoặc "json"
            target_word_range: Range từ cho scoring

        Returns:
            ExperimentResult
        """
        _log.info(f"Running Prompt A/B: '{variant_a.name}' vs '{variant_b.name}'")

        llm = self._build_llm(provider="google", model=self.settings.PRIMARY_MODEL)

        # --- Variant A ---
        output_a, latency_a = self._invoke_variant(
            llm, variant_a.prompt_template, input_data, output_parser
        )

        # --- Variant B ---
        output_b, latency_b = self._invoke_variant(
            llm, variant_b.prompt_template, input_data, output_parser
        )

        # --- Evaluate ---
        from tests.ab_testing.evaluator import OutputEvaluator
        evaluator = OutputEvaluator()

        if output_parser == "str":
            score_a = evaluator.evaluate_summary(
                str(output_a), variant_a.name, latency_a, target_word_range=target_word_range
            )
            score_b = evaluator.evaluate_summary(
                str(output_b), variant_b.name, latency_b, target_word_range=target_word_range
            )
        else:
            kw_a = output_a if isinstance(output_a, list) else output_a.get("keywords", [])
            kw_b = output_b if isinstance(output_b, list) else output_b.get("keywords", [])
            score_a = evaluator.evaluate_keywords(kw_a, variant_a.name, latency_a)
            score_b = evaluator.evaluate_keywords(kw_b, variant_b.name, latency_b)

        comparison = evaluator.compare(score_a, score_b)

        result = ExperimentResult(
            experiment_name=self.name,
            variant_a_name=variant_a.name,
            variant_b_name=variant_b.name,
            variant_a_output=str(output_a)[:2000],
            variant_b_output=str(output_b)[:2000],
            variant_a_latency_ms=latency_a,
            variant_b_latency_ms=latency_b,
            variant_a_score=score_a.auto_score,
            variant_b_score=score_b.auto_score,
            winner=comparison["winner"],
            margin=comparison["margin"],
            verdict=comparison["verdict"],
            timestamp=datetime.now(_VN_TZ).isoformat(),
            input_summary=f"Keys: {list(input_data.keys())}, total_chars: {sum(len(str(v)) for v in input_data.values())}",
        )

        self.results.append(result)
        self._save_result(result)

        _log.info(
            f"Prompt A/B done: {result.winner} wins "
            f"(A={score_a.auto_score}, B={score_b.auto_score}, margin={result.margin})"
        )

        return result

    # ------------------------------------------------------------------
    #  Experiment Type 2: Model A/B (Cùng prompt, khác model)
    # ------------------------------------------------------------------

    def run_model_ab(
        self,
        variant_a,  # ModelVariant
        variant_b,  # ModelVariant
        prompt_template: str,
        input_data: dict,
        output_parser: str = "str",
        target_word_range: tuple[int, int] = (200, 400),
    ) -> ExperimentResult:
        """
        Chạy cùng 1 prompt trên 2 models khác nhau.

        Args:
            variant_a, variant_b: ModelVariant objects
            prompt_template: Prompt template chung
            input_data: dict template variables
            output_parser: "str" | "json"

        Returns:
            ExperimentResult
        """
        _log.info(f"Running Model A/B: '{variant_a.name}' vs '{variant_b.name}'")

        # --- Variant A ---
        llm_a = self._build_llm(
            provider=variant_a.provider,
            model=variant_a.model_name,
            temperature=variant_a.temperature,
            max_tokens=variant_a.max_tokens,
        )
        output_a, latency_a = self._invoke_variant(
            llm_a, prompt_template, input_data, output_parser
        )

        # --- Variant B ---
        llm_b = self._build_llm(
            provider=variant_b.provider,
            model=variant_b.model_name,
            temperature=variant_b.temperature,
            max_tokens=variant_b.max_tokens,
        )
        output_b, latency_b = self._invoke_variant(
            llm_b, prompt_template, input_data, output_parser
        )

        # --- Evaluate ---
        from tests.ab_testing.evaluator import OutputEvaluator
        evaluator = OutputEvaluator()

        score_a = evaluator.evaluate_summary(
            str(output_a), variant_a.name, latency_a, target_word_range=target_word_range
        )
        score_b = evaluator.evaluate_summary(
            str(output_b), variant_b.name, latency_b, target_word_range=target_word_range
        )

        comparison = evaluator.compare(score_a, score_b)

        result = ExperimentResult(
            experiment_name=self.name,
            variant_a_name=variant_a.name,
            variant_b_name=variant_b.name,
            variant_a_output=str(output_a)[:2000],
            variant_b_output=str(output_b)[:2000],
            variant_a_latency_ms=latency_a,
            variant_b_latency_ms=latency_b,
            variant_a_score=score_a.auto_score,
            variant_b_score=score_b.auto_score,
            winner=comparison["winner"],
            margin=comparison["margin"],
            verdict=comparison["verdict"],
            timestamp=datetime.now(_VN_TZ).isoformat(),
            input_summary=f"Model A: {variant_a.model_name}, Model B: {variant_b.model_name}",
            metadata={
                "model_a": variant_a.model_name,
                "model_b": variant_b.model_name,
                "temperature_a": variant_a.temperature,
                "temperature_b": variant_b.temperature,
            },
        )

        self.results.append(result)
        self._save_result(result)

        _log.info(
            f"Model A/B done: {result.winner} wins "
            f"(A={score_a.auto_score}, B={score_b.auto_score})"
        )

        return result

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _build_llm(
        self,
        provider: str = "google",
        model: str = "gemini-2.0-flash",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ):
        """Build LLM instance cho experiment."""
        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=self.settings.GEMINI_API_KEY,
                temperature=temperature,
                max_output_tokens=max_tokens,
                timeout=self.settings.API_TIMEOUT_SECONDS,
            )
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=self.settings.OPENAI_API_KEY,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.settings.API_TIMEOUT_SECONDS,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def _invoke_variant(llm, prompt_template: str, input_data: dict, output_parser: str) -> tuple:
        """
        Invoke 1 variant và đo latency.
        Có cơ chế bao lỗi và tự động chờ (sleep) nếu dính Rate Limit 429.
        Returns: (output, latency_ms)
        """
        prompt = ChatPromptTemplate.from_template(prompt_template)

        if output_parser == "json":
            chain = prompt | llm | JsonOutputParser()
        else:
            chain = prompt | llm | StrOutputParser()

        retries = 5
        import re
        for attempt in range(retries):
            start = time.perf_counter()
            try:
                output = chain.invoke(input_data)
                latency = round((time.perf_counter() - start) * 1000, 2)
                return output, latency
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt < retries - 1:
                        wait_time = 60  # Default safe wait
                        match = re.search(r'retry in ([\d\.]+)s', error_str)
                        if match:
                            wait_time = int(float(match.group(1))) + 5
                            
                        _log.warning(f"Rate limit hit! API requested {wait_time-5}s. Sleeping {wait_time}s... (Attempt {attempt+1}/{retries})")
                        time.sleep(wait_time)
                        continue

                _log.error(f"Variant invocation failed after {attempt+1} attempts: {e}")
                output = f"ERROR: {type(e).__name__}: {e}"
                latency = round((time.perf_counter() - start) * 1000, 2)
                return output, latency

    def _save_result(self, result: ExperimentResult) -> None:
        """Lưu kết quả experiment ra JSON."""
        timestamp = datetime.now(_VN_TZ).strftime("%Y%m%d_%H%M%S")
        filename = f"{self.name}_{timestamp}.json"
        filepath = self.results_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        _log.info(f"Experiment result saved: {filepath}")

    def load_all_results(self) -> list[dict]:
        """Load tất cả results cho experiment này."""
        results = []
        for f in sorted(self.results_dir.glob(f"{self.name}_*.json")):
            with open(f, "r", encoding="utf-8") as fp:
                results.append(json.load(fp))
        return results

    def generate_report(self) -> str:
        """Sinh báo cáo A/B Testing dạng Markdown."""
        all_results = self.load_all_results()

        if not all_results:
            return f"# A/B Test Report: {self.name}\n\nKhông có kết quả nào."

        md = f"# 🧪 A/B Test Report: {self.name}\n\n"
        md += f"**Tổng số experiments:** {len(all_results)}\n\n"
        md += "---\n\n"

        # Summary table
        md += "## Kết Quả Tổng Hợp\n\n"
        md += "| # | Variant A | Variant B | Score A | Score B | Winner | Margin |\n"
        md += "|---|-----------|-----------|---------|---------|--------|--------|\n"

        wins = {}
        for i, r in enumerate(all_results, 1):
            md += (
                f"| {i} | {r['variant_a_name']} | {r['variant_b_name']} | "
                f"{r['variant_a_score']} | {r['variant_b_score']} | "
                f"**{r['winner']}** | {r['margin']} |\n"
            )
            winner = r.get("winner", "TIE")
            wins[winner] = wins.get(winner, 0) + 1

        md += "\n---\n\n"

        # Win count
        md += "## Thống Kê Thắng/Thua\n\n"
        for name, count in sorted(wins.items(), key=lambda x: -x[1]):
            bar = "█" * count
            md += f"- **{name}**: {count} lần thắng {bar}\n"

        md += "\n---\n\n"

        # Detailed outputs
        md += "## Chi Tiết Output\n\n"
        for i, r in enumerate(all_results, 1):
            md += f"### Experiment #{i} ({r.get('timestamp', 'N/A')})\n\n"

            md += f"**Variant A ({r['variant_a_name']})** — Score: {r['variant_a_score']} | Latency: {r['variant_a_latency_ms']}ms\n"
            md += f"> {r['variant_a_output'][:500]}...\n\n"

            md += f"**Variant B ({r['variant_b_name']})** — Score: {r['variant_b_score']} | Latency: {r['variant_b_latency_ms']}ms\n"
            md += f"> {r['variant_b_output'][:500]}...\n\n"

            md += f"📊 **Verdict:** {r.get('verdict', 'N/A')}\n\n---\n\n"

        md += f"\n*Report generated: {datetime.now(_VN_TZ).isoformat()}*\n"
        return md
