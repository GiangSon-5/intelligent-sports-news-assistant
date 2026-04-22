"""
Tests — test_crawler.py
Unit tests for Crawler module (items, pipelines, date parsing).
Covers: validation, date normalization, dedup, edge cases từ SPEC §6.
"""

import hashlib
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from scrapy.exceptions import DropItem


# ---------------------------------------------------------------------------
#  Test NewsArticleItem
# ---------------------------------------------------------------------------

class TestNewsArticleItem:
    """Test Scrapy Item schema."""

    def test_item_has_all_fields(self):
        """Item has exactly 7 fields according to Global Data Contract."""
        from crawler.news_crawler.items import NewsArticleItem
        item = NewsArticleItem()
        expected_fields = ["title", "content", "publish_date", "source", "url", "crawled_at", "article_id"]
        for field in expected_fields:
            assert field in item.fields, f"Missing field: {field}"

    def test_item_accepts_valid_data(self):
        """Item accepts valid data."""
        from crawler.news_crawler.items import NewsArticleItem
        item = NewsArticleItem(
            title="Test Title",
            content="Test Content that is long enough",
            publish_date="2026-04-14T20:30:00+07:00",
            source="vnexpress",
            url="https://vnexpress.net/test.html",
            crawled_at="2026-04-20T06:00:00+07:00",
            article_id="abc123",
        )
        assert item["title"] == "Test Title"
        assert item["source"] == "vnexpress"


# ---------------------------------------------------------------------------
#  Test ValidationPipeline
# ---------------------------------------------------------------------------

class TestValidationPipeline:
    """Test pipeline validation logic."""

    @pytest.fixture
    def pipeline(self):
        from crawler.news_crawler.pipelines import ValidationPipeline
        return ValidationPipeline()

    @pytest.fixture
    def valid_item(self):
        return {
            "title": "Đội tuyển Việt Nam thắng Thái Lan 2-1",
            "content": "Trong trận đấu căng thẳng tối ngày 14/4 tại sân Mỹ Đình, đội tuyển Việt Nam đã giành chiến thắng kịch tính 2-1 trước đối thủ truyền kiếp.",
            "url": "https://vnexpress.net/test.html",
        }

    def test_valid_item_passes(self, pipeline, valid_item):
        """Valid item → passes through."""
        spider = MagicMock()
        result = pipeline.process_item(valid_item, spider)
        assert result["title"] == valid_item["title"]

    def test_missing_title_drops(self, pipeline, valid_item):
        """Edge Case #1: Missing title → DropItem."""
        valid_item["title"] = ""
        spider = MagicMock()
        with pytest.raises(DropItem):
            pipeline.process_item(valid_item, spider)

    def test_missing_content_drops(self, pipeline, valid_item):
        """Edge Case #4: Missing content (video-only) → DropItem."""
        valid_item["content"] = ""
        spider = MagicMock()
        with pytest.raises(DropItem):
            pipeline.process_item(valid_item, spider)

    def test_short_content_drops(self, pipeline, valid_item):
        """Edge Case #10: Content < 100 chars (paywall) → DropItem."""
        valid_item["content"] = "Too short"
        spider = MagicMock()
        with pytest.raises(DropItem):
            pipeline.process_item(valid_item, spider)

    def test_missing_url_drops(self, pipeline, valid_item):
        """Missing URL → DropItem."""
        valid_item["url"] = ""
        spider = MagicMock()
        with pytest.raises(DropItem):
            pipeline.process_item(valid_item, spider)


# ---------------------------------------------------------------------------
#  Test DateNormalizationPipeline
# ---------------------------------------------------------------------------

class TestDateNormalizationPipeline:
    """Test Vietnamese date parsing."""

    @pytest.fixture
    def pipeline(self):
        from crawler.news_crawler.pipelines import DateNormalizationPipeline
        return DateNormalizationPipeline()

    def test_parse_dd_mm_yyyy_time(self, pipeline):
        """Parse: '14/04/2026 20:30'."""
        item = {"publish_date": "14/04/2026 20:30", "crawled_at": "2026-04-20T06:00:00+07:00", "url": "test"}
        spider = MagicMock()
        result = pipeline.process_item(item, spider)
        assert "2026-04-14" in result["publish_date"]

    def test_parse_vietnamese_date_with_day_name(self, pipeline):
        """Parse: 'Chủ nhật, 14/4/2026, 20:30 (GMT+7)'."""
        item = {"publish_date": "Chủ nhật, 14/4/2026, 20:30 (GMT+7)", "crawled_at": "2026-04-20T06:00:00+07:00", "url": "test"}
        spider = MagicMock()
        result = pipeline.process_item(item, spider)
        assert "2026-04-14" in result["publish_date"]

    def test_parse_already_iso(self, pipeline):
        """Parse: Already ISO 8601 → keep as is."""
        iso_date = "2026-04-14T20:30:00+07:00"
        item = {"publish_date": iso_date, "crawled_at": "2026-04-20T06:00:00+07:00", "url": "test"}
        spider = MagicMock()
        result = pipeline.process_item(item, spider)
        assert result["publish_date"] == iso_date

    def test_parse_relative_hours(self, pipeline):
        """Parse: '3 giờ trước'."""
        item = {"publish_date": "3 giờ trước", "crawled_at": "2026-04-20T06:00:00+07:00", "url": "test"}
        spider = MagicMock()
        result = pipeline.process_item(item, spider)
        assert "T" in result["publish_date"]  # ISO format

    def test_parse_relative_days(self, pipeline):
        """Parse: '2 ngày trước'."""
        item = {"publish_date": "2 ngày trước", "crawled_at": "2026-04-20T06:00:00+07:00", "url": "test"}
        spider = MagicMock()
        result = pipeline.process_item(item, spider)
        assert "T" in result["publish_date"]

    def test_unparseable_returns_none(self, pipeline):
        """Edge Case #5: Strange format → return None to ensure data integrity."""
        crawled = "2026-04-20T06:00:00+07:00"
        item = {"publish_date": "unknown_format_xyz", "crawled_at": crawled, "url": "test"}
        spider = MagicMock()
        result = pipeline.process_item(item, spider)
        assert result["publish_date"] is None


# ---------------------------------------------------------------------------
#  Test DeduplicationPipeline
# ---------------------------------------------------------------------------

class TestDeduplicationPipeline:
    """Test deduplication logic."""

    @pytest.fixture
    def pipeline(self):
        from crawler.news_crawler.pipelines import DeduplicationPipeline
        return DeduplicationPipeline()

    def test_unique_items_pass(self, pipeline):
        """2 items with different article_id → both pass."""
        spider = MagicMock()
        item1 = {"article_id": "abc123", "url": "https://test.com/1"}
        item2 = {"article_id": "def456", "url": "https://test.com/2"}

        pipeline.process_item(item1, spider)
        pipeline.process_item(item2, spider)
        assert len(pipeline.seen_ids) == 2

    def test_duplicate_item_dropped(self, pipeline):
        """Edge Case #6: Duplicate article_id → DropItem."""
        spider = MagicMock()
        item1 = {"article_id": "abc123", "url": "https://test.com/1"}
        item2 = {"article_id": "abc123", "url": "https://test.com/1"}

        pipeline.process_item(item1, spider)
        with pytest.raises(DropItem):
            pipeline.process_item(item2, spider)

    def test_generates_id_if_missing(self, pipeline):
        """empty article_id → auto-generate from SHA256(url)."""
        spider = MagicMock()
        url = "https://vnexpress.net/test.html"
        item = {"article_id": "", "url": url}

        result = pipeline.process_item(item, spider)
        expected_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
        assert result["article_id"] == expected_id
