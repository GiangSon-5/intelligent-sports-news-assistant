"""
Tests — test_reporting.py
Unit tests for Reporting module (markdown_generator.py, pdf_exporter.py).
Covers: Jinja2 rendering, custom filters, edge cases, PDF availability check.
"""

import pytest
from pathlib import Path

from reporting.markdown_generator import MarkdownReportGenerator
from reporting.pdf_exporter import PdfExporter


@pytest.fixture
def report_data():
    """Sample report_data matching SPEC §2.1 input schema."""
    return {
        "ai_result": {
            "executive_summary": "Tuần qua, bóng đá Việt Nam tiếp tục là tâm điểm với chiến thắng lịch sử 2-1 trước Thái Lan.",
            "trending_keywords": [
                {"keyword": "AFF Cup 2026", "frequency": 45, "category": "football"},
                {"keyword": "Nguyễn Tiến Linh", "frequency": 32, "category": "football"},
                {"keyword": "Monte Carlo Masters", "frequency": 18, "category": "tennis"},
            ],
            "highlighted_news": [
                {
                    "title": "Đội tuyển Việt Nam thắng Thái Lan 2-1",
                    "summary": "Trận thắng kịch tính với bàn quyết định phút 89.",
                    "url": "https://vnexpress.net/test.html",
                    "source": "vnexpress",
                    "relevance_score": 0.98,
                },
                {
                    "title": "Hoàng Đức giành Quả bóng Vàng",
                    "summary": "Tiền vệ Hoàng Đức nhận 85% số phiếu bầu.",
                    "url": "https://thanhnien.vn/test.htm",
                    "source": "thanhnien",
                    "relevance_score": 0.92,
                },
            ],
            "model_used": "gemini-2.0-flash",
        },
        "analysis": {
            "total_articles": 208,
            "articles_per_source": {"vnexpress": 80, "thanhnien": 68, "tuoitre": 60},
            "date_range": {"from": "2026-04-14", "to": "2026-04-20"},
            "source_list": ["vnexpress", "thanhnien", "tuoitre"],
        },
        "report_metadata": {
            "generated_at": "2026-04-20T06:15:00+07:00",
            "report_version": "1.0",
        },
    }


@pytest.fixture
def empty_report_data():
    """Report data with all sections empty (Edge Cases #1-#3). Surrounding text will be English."""
    return {
        "ai_result": {
            "executive_summary": "",
            "trending_keywords": [],
            "highlighted_news": [],
            "model_used": "gemini-2.0-flash",
        },
        "analysis": {
            "total_articles": 0,
            "articles_per_source": {},
            "date_range": {"from": "N/A", "to": "N/A"},
            "source_list": [],
        },
        "report_metadata": {
            "generated_at": "2026-04-20T06:15:00+07:00",
            "report_version": "1.0",
        },
    }


# ---------------------------------------------------------------------------
#  Test MarkdownReportGenerator
# ---------------------------------------------------------------------------

class TestMarkdownReportGenerator:
    """Test Jinja2-based Markdown generation."""

    def test_generate_returns_string(self, report_data):
        """generate() returns a string."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_report_contains_title(self, report_data):
        """Report contains main title."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "Weekly Sports News Summary Report" in result

    def test_report_contains_executive_summary(self, report_data):
        """Section 1: Executive Summary is present."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "Executive Summary" in result
        assert "bóng đá Việt Nam" in result

    def test_report_contains_keywords_table(self, report_data):
        """Section 2: Trending Keywords table is present."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "Trending Keywords" in result
        assert "AFF Cup 2026" in result
        assert "45" in result

    def test_report_contains_highlighted_news(self, report_data):
        """Section 3: Highlighted News is present."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "Highlighted News" in result
        assert "Đội tuyển Việt Nam thắng Thái Lan 2-1" in result
        assert "0.98" in result
        assert "https://vnexpress.net/test.html" in result

    def test_report_contains_metadata(self, report_data):
        """Report contains date range, total articles, sources."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "2026-04-14" in result
        assert "2026-04-20" in result
        assert "208" in result

    def test_report_contains_footer(self, report_data):
        """Footer: model name + generated timestamp."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "gemini-2.0-flash" in result
        assert "Intelligent Sports News Assistant" in result

    def test_report_has_all_3_sections(self, report_data):
        """Report MUST have all 3 sections (SRS Rule #3)."""
        gen = MarkdownReportGenerator()
        result = gen.generate(report_data)
        assert "## 1." in result  # Executive Summary
        assert "## 2." in result  # Trending Keywords
        assert "## 3." in result  # Highlighted News

    # --- Edge Cases ---

    def test_empty_summary_shows_fallback(self, empty_report_data):
        """Edge Case #1: Empty executive_summary → fallback text."""
        gen = MarkdownReportGenerator()
        result = gen.generate(empty_report_data)
        assert "No Executive Summary data available for this period." in result

    def test_empty_keywords_shows_fallback(self, empty_report_data):
        """Edge Case #2: Empty keywords → fallback text."""
        gen = MarkdownReportGenerator()
        result = gen.generate(empty_report_data)
        assert "No prominent keywords extracted." in result

    def test_empty_news_shows_fallback(self, empty_report_data):
        """Edge Case #3: Empty highlighted_news → fallback text."""
        gen = MarkdownReportGenerator()
        result = gen.generate(empty_report_data)
        assert "No highlighted articles for this week." in result

    def test_missing_ai_result_graceful(self):
        """Completely missing ai_result → no crash."""
        gen = MarkdownReportGenerator()
        data = {
            "ai_result": {},
            "analysis": {"total_articles": 0, "date_range": {"from": "", "to": ""}, "articles_per_source": {}},
            "report_metadata": {"generated_at": "", "report_version": "1.0"},
        }
        result = gen.generate(data)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
#  Test Custom Jinja2 Filters
# ---------------------------------------------------------------------------

class TestJinjaFilters:
    """Test custom Jinja2 filters."""

    def test_category_emoji_football(self):
        """football → ⚽ Football."""
        result = MarkdownReportGenerator._category_emoji("football")
        assert "⚽" in result
        assert "Football" in result

    def test_category_emoji_tennis(self):
        """tennis → 🎾 Tennis."""
        result = MarkdownReportGenerator._category_emoji("tennis")
        assert "🎾" in result

    def test_category_emoji_esports(self):
        """esports → 🎮 E-Sports."""
        result = MarkdownReportGenerator._category_emoji("esports")
        assert "🎮" in result

    def test_category_emoji_unknown(self):
        """Unknown category → 🏆 Other."""
        result = MarkdownReportGenerator._category_emoji("xyz")
        assert "Other" in result

    def test_source_display_vnexpress(self):
        """vnexpress → VnExpress."""
        assert MarkdownReportGenerator._source_display_name("vnexpress") == "VnExpress"

    def test_source_display_thanhnien(self):
        """thanhnien → Thanh Niên."""
        assert MarkdownReportGenerator._source_display_name("thanhnien") == "Thanh Niên"

    def test_source_display_tuoitre(self):
        """tuoitre → Tuổi Trẻ."""
        assert MarkdownReportGenerator._source_display_name("tuoitre") == "Tuổi Trẻ"

    def test_source_display_unknown(self):
        """Unknown source → title case."""
        assert MarkdownReportGenerator._source_display_name("newssite") == "Newssite"

    def test_escape_markdown_pipe(self):
        """Escape | in Markdown titles (Edge Case #5)."""
        result = MarkdownReportGenerator._escape_markdown("Title | with pipe")
        assert "\\|" in result

    def test_escape_markdown_empty(self):
        """Empty string → empty string."""
        assert MarkdownReportGenerator._escape_markdown("") == ""


# ---------------------------------------------------------------------------
#  Test PdfExporter
# ---------------------------------------------------------------------------

class TestPdfExporter:
    """Test PDF export functionality."""

    def test_pdf_exporter_init(self):
        """Init không crash bất kể WeasyPrint có sẵn hay không."""
        exporter = PdfExporter()
        assert isinstance(exporter.is_available, bool)

    def test_pdf_export_without_weasyprint(self):
        """Edge Case #6: WeasyPrint chưa cài → ImportError."""
        exporter = PdfExporter()
        if not exporter.is_available:
            with pytest.raises(ImportError):
                exporter.export("# Test", "test.pdf")

    def test_pdf_export_with_weasyprint(self, tmp_path):
        """Nếu WeasyPrint available → tạo PDF file."""
        exporter = PdfExporter()
        if exporter.is_available:
            md_content = "# Test Report\n\nThis is a test report."
            output = str(tmp_path / "test_report.pdf")
            result = exporter.export(md_content, output)
            assert Path(result).exists()
            assert Path(result).stat().st_size > 0
        else:
            pytest.skip("WeasyPrint not installed")
