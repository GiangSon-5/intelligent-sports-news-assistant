"""
Reporting Module — markdown_generator.py
Jinja2-based Markdown report generator according to SPEC §3.2.
Custom filters: category_emoji, source_display_name, escape_markdown.
"""

import re
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from logger import get_logger, log_function

_log = get_logger("reporting.markdown")


class MarkdownReportGenerator:
    """
    Generate Weekly Summary Report in Markdown format from AI results + analysis.
    Uses Jinja2 template engine.
    """

    def __init__(self, template_dir: str = None):
        """
        Args:
            template_dir: Path to the directory containing Jinja2 templates.
                          Default: reporting/templates/ (relative to project root).
        """
        if template_dir is None:
            template_dir = str(Path(__file__).parent / "templates")

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # Markdown — không auto-escape HTML
        )
        self._register_filters()

        _log.info(f"MarkdownReportGenerator initialized | template_dir={template_dir}")

    # ------------------------------------------------------------------
    #  Custom Jinja2 Filters (SPEC §3.2)
    # ------------------------------------------------------------------

    def _register_filters(self) -> None:
        """Register custom filters for the Jinja2 environment."""
        self.env.filters["category_emoji"] = self._category_emoji
        self.env.filters["source_display_name"] = self._source_display_name
        self.env.filters["escape_markdown"] = self._escape_markdown

    @staticmethod
    def _category_emoji(category: str) -> str:
        """Map sport category → emoji display string (SPEC §3.2)."""
        emoji_map = {
            "football": "⚽ Football",
            "basketball": "🏀 Basketball",
            "tennis": "🎾 Tennis",
            "esports": "🎮 E-Sports",
            "swimming": "🏊 Swimming",
            "athletics": "🏃 Athletics",
            "multi-sport": "🏅 Multi-Sport",
            "other": "🏆 Other",
        }
        return emoji_map.get(str(category).lower(), "🏆 Other")

    @staticmethod
    def _source_display_name(source: str) -> str:
        """Map source slug → display name (SPEC §3.2)."""
        name_map = {
            "vnexpress": "VnExpress",
            "thanhnien": "Thanh Niên",
            "tuoitre": "Tuổi Trẻ",
        }
        return name_map.get(str(source).lower(), source.title())

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape special Markdown characters in the title (Edge Case #5)."""
        if not text:
            return text
        # Escape: | * # [ ] ( ) ` _
        text = text.replace("|", "\\|")
        return text

    # ------------------------------------------------------------------
    #  Main Generate Method
    # ------------------------------------------------------------------

    @log_function("reporting.markdown")
    def generate(self, report_data: dict) -> str:
        """
        Render Markdown report from report_data.

        Args:
            report_data: dict containing ai_result, analysis, report_metadata
                         (SPEC §2.1 input schema)

        Returns:
            str: Rendered Markdown content

        Raises:
            TemplateNotFound: If template file does not exist (Edge Case SRS #1)
        """
        start = time.perf_counter()

        # Load template (Edge Case SRS #1: TemplateNotFoundError)
        try:
            template = self.env.get_template("weekly_report.md.j2")
        except TemplateNotFound:
            _log.error("Template 'weekly_report.md.j2' not found!")
            raise

        # Extract data safely (Edge Case SRS #2: missing sections → fallback)
        ai_result = report_data.get("ai_result", {})
        analysis = report_data.get("analysis", {})
        metadata = report_data.get("report_metadata", {})

        # Build template context
        date_range = analysis.get("date_range", {})
        articles_per_source = analysis.get("articles_per_source", {})
        source_list = analysis.get("source_list", list(articles_per_source.keys()))

        # Source display names
        source_display_map = {
            "vnexpress": "VnExpress",
            "thanhnien": "Thanh Niên",
            "tuoitre": "Tuổi Trẻ",
        }
        sources_display = [source_display_map.get(s, s.title()) for s in source_list]

        generated_at_raw = metadata.get("generated_at", "")
        generated_date = generated_at_raw[:10] if generated_at_raw else "N/A"

        context = {
            "date_from": date_range.get("from", "N/A"),
            "date_to": date_range.get("to", "N/A"),
            "generated_date": generated_date,
            "total_articles": analysis.get("total_articles", 0),
            "sources": sources_display,
            "executive_summary": ai_result.get("executive_summary", ""),
            "trending_keywords": ai_result.get("trending_keywords", []),
            "highlighted_news": ai_result.get("highlighted_news", []),
            "model_used": ai_result.get("model_used", "N/A"),
            "generated_at": generated_at_raw or "N/A",
        }

        # Ensure relevance_score is float for formatting
        for news in context["highlighted_news"]:
            score = news.get("relevance_score", 0)
            try:
                news["relevance_score"] = float(score)
            except (ValueError, TypeError):
                news["relevance_score"] = 0.0

        # Render
        md_content = template.render(**context)

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"Markdown report generated | "
            f"length={len(md_content)} chars | "
            f"keywords={len(context['trending_keywords'])} | "
            f"highlights={len(context['highlighted_news'])} | "
            f"latency={elapsed}ms"
        )

        return md_content
