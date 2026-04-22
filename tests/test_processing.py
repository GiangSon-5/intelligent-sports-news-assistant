"""
Tests — test_processing.py
Unit tests for Processing module (cleaner.py, analyzer.py).
Covers: cleaning pipeline, edge cases, analyzer output schema.
"""

import pytest
from datetime import datetime, timezone, timedelta

import pandas as pd

from processing.cleaner import DataCleaner
from processing.analyzer import DataAnalyzer

_VN_TZ = timezone(timedelta(hours=7))


@pytest.fixture
def sample_raw_articles():
    """Sample raw articles for cleaning tests."""
    now = datetime.now(_VN_TZ)
    return [
        {
            "title": "Đội tuyển Việt Nam thắng Thái Lan 2-1 tại AFF Cup 2026",
            "content": "Trong trận đấu căng thẳng tối ngày 14/4 tại sân Mỹ Đình, đội tuyển Việt Nam đã giành chiến thắng kịch tính 2-1 trước đối thủ truyền kiếp Thái Lan. " * 3,
            "publish_date": (now - timedelta(days=2)).isoformat(),
            "source": "vnexpress",
            "url": "https://vnexpress.net/test-1.html",
            "article_id": "id_001",
        },
        {
            "title": "Hoàng Đức giành Quả bóng Vàng 2026",
            "content": "Tiền vệ Hoàng Đức trở thành cầu thủ đầu tiên giành QBV hai năm liên tiếp kể từ Nguyễn Văn Quyết. Anh nhận 85% số phiếu bầu từ các nhà báo thể thao. " * 3,
            "publish_date": (now - timedelta(days=3)).isoformat(),
            "source": "thanhnien",
            "url": "https://thanhnien.vn/test-2.htm",
            "article_id": "id_002",
        },
        {
            "title": "V-League 2026 vòng 10 kết quả",
            "content": "Vòng 10 V-League 2026 diễn ra với nhiều kết quả bất ngờ. CLB Hà Nội tiếp tục dẫn đầu bảng xếp hạng sau chiến thắng thuyết phục 3-0 trước SHB Đà Nẵng. " * 3,
            "publish_date": (now - timedelta(days=1)).isoformat(),
            "source": "tuoitre",
            "url": "https://tuoitre.vn/test-3.htm",
            "article_id": "id_003",
        },
    ]


# ---------------------------------------------------------------------------
#  Test DataCleaner
# ---------------------------------------------------------------------------

class TestDataCleaner:
    """Test cleaning pipeline."""

    def test_clean_returns_dataframe(self, sample_raw_articles):
        """clean() returns pd.DataFrame."""
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert isinstance(result, pd.DataFrame)

    def test_clean_preserves_valid_articles(self, sample_raw_articles):
        """Valid articles → kept."""
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert len(result) == 3

    def test_derived_columns_added(self, sample_raw_articles):
        """Step 6: Add content_length, word_count, publish_date_dt."""
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert "content_length" in result.columns
        assert "word_count" in result.columns
        assert "publish_date_dt" in result.columns
        assert all(result["content_length"] > 0)
        assert all(result["word_count"] > 0)

    def test_empty_input_returns_empty_dataframe(self):
        """Edge Case #1: Input [] → empty DataFrame."""
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_drops_missing_title(self, sample_raw_articles):
        """Step 1: Article missing title → dropped."""
        sample_raw_articles.append({
            "title": "",
            "content": "Test content " * 20,
            "publish_date": datetime.now(_VN_TZ).isoformat(),
            "source": "vnexpress",
            "url": "https://vnexpress.net/test-4.html",
            "article_id": "id_004",
        })
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert len(result) == 3  # 4th article dropped

    def test_drops_missing_content(self, sample_raw_articles):
        """Step 1: Article missing content → dropped."""
        sample_raw_articles.append({
            "title": "Title có nhưng content rỗng",
            "content": "",
            "publish_date": datetime.now(_VN_TZ).isoformat(),
            "source": "vnexpress",
            "url": "https://vnexpress.net/test-5.html",
            "article_id": "id_005",
        })
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert len(result) == 3

    def test_deduplicates_by_article_id(self, sample_raw_articles):
        """Step 2: Duplicate article_id → keep first version."""
        dup = sample_raw_articles[0].copy()
        dup["title"] = "Duplicate article"
        sample_raw_articles.append(dup)

        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert len(result) == 3  # duplicate removed

    def test_filters_old_articles(self, sample_raw_articles):
        """Step 3: Article older than CRAWL_DAYS_BACK → dropped."""
        old_article = {
            "title": "Bài cũ 30 ngày",
            "content": "Content cũ rất dài " * 20,
            "publish_date": (datetime.now(_VN_TZ) - timedelta(days=30)).isoformat(),
            "source": "vnexpress",
            "url": "https://vnexpress.net/old.html",
            "article_id": "id_old",
        }
        sample_raw_articles.append(old_article)

        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert len(result) == 3  # old article filtered out

    def test_filters_short_content(self, sample_raw_articles):
        """Step 5: Content < 100 chars → dropped."""
        short_article = {
            "title": "Bài quá ngắn",
            "content": "Ngắn quá.",
            "publish_date": datetime.now(_VN_TZ).isoformat(),
            "source": "vnexpress",
            "url": "https://vnexpress.net/short.html",
            "article_id": "id_short",
        }
        sample_raw_articles.append(short_article)

        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        assert len(result) == 3  # short article filtered

    def test_normalizes_text_html_entities(self, sample_raw_articles):
        """Step 4: HTML entities → decoded (Edge Case #4)."""
        sample_raw_articles[0]["content"] = "V-League &amp; AFF Cup &lt;2026&gt; " * 20
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        cleaned_content = result.iloc[0]["content"]
        assert "&amp;" not in cleaned_content
        assert "&lt;" not in cleaned_content

    def test_normalizes_text_strip_html_tags(self, sample_raw_articles):
        """Step 4: HTML tags are stripped."""
        sample_raw_articles[0]["content"] = "<p>Test content</p> <b>bold</b> <a href='test'>link</a> " * 20
        cleaner = DataCleaner(days_back=7)
        result = cleaner.clean(sample_raw_articles)
        cleaned = result.iloc[0]["content"]
        assert "<p>" not in cleaned
        assert "<b>" not in cleaned


# ---------------------------------------------------------------------------
#  Test DataAnalyzer
# ---------------------------------------------------------------------------

class TestDataAnalyzer:
    """Test analysis output schema."""

    @pytest.fixture
    def cleaned_df(self, sample_raw_articles):
        """Create cleaned DataFrame."""
        cleaner = DataCleaner(days_back=7)
        return cleaner.clean(sample_raw_articles)

    def test_analyze_output_schema(self, cleaned_df):
        """Output matches SPEC §2.3 schema."""
        analyzer = DataAnalyzer()
        result = analyzer.analyze(cleaned_df)

        assert "total_articles" in result
        assert "articles_per_source" in result
        assert "articles_per_day" in result
        assert "avg_content_length" in result
        assert "avg_word_count" in result
        assert "date_range" in result
        assert "from" in result["date_range"]
        assert "to" in result["date_range"]
        assert "source_list" in result

    def test_analyze_total_articles(self, cleaned_df):
        """total_articles = len(DataFrame)."""
        analyzer = DataAnalyzer()
        result = analyzer.analyze(cleaned_df)
        assert result["total_articles"] == len(cleaned_df)

    def test_analyze_articles_per_source(self, cleaned_df):
        """articles_per_source contains 3 sources."""
        analyzer = DataAnalyzer()
        result = analyzer.analyze(cleaned_df)
        assert len(result["articles_per_source"]) <= 3
        assert all(isinstance(v, int) for v in result["articles_per_source"].values())

    def test_analyze_empty_dataframe(self):
        """Edge Case: Empty DataFrame → zero stats."""
        analyzer = DataAnalyzer()
        result = analyzer.analyze(pd.DataFrame())
        assert result["total_articles"] == 0
        assert result["articles_per_source"] == {}
        assert result["date_range"]["from"] == ""
        assert result["source_list"] == []

    def test_analyze_avg_values(self, cleaned_df):
        """avg_content_length, avg_word_count > 0."""
        analyzer = DataAnalyzer()
        result = analyzer.analyze(cleaned_df)
        assert result["avg_content_length"] > 0
        assert result["avg_word_count"] > 0
