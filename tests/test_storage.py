"""
Tests — test_storage.py
Unit tests cho Storage module (storage/json_store.py).
Covers: CRUD operations, atomic writes, edge cases từ SPEC §6.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from storage.json_store import JsonFileStore, StorageError


@pytest.fixture
def tmp_store(tmp_path):
    """Tạo JsonFileStore với thư mục tạm."""
    store = JsonFileStore(base_dir=str(tmp_path / "storage"))
    return store


@pytest.fixture
def sample_articles():
    """Sample articles khớp Global Data Contract."""
    return [
        {
            "title": "Đội tuyển Việt Nam thắng Thái Lan 2-1",
            "content": "Trong trận đấu căng thẳng tối ngày 14/4 tại sân Mỹ Đình, đội tuyển Việt Nam đã giành chiến thắng kịch tính 2-1 trước đối thủ truyền kiếp Thái Lan.",
            "publish_date": "2026-04-14T20:30:00+07:00",
            "source": "vnexpress",
            "url": "https://vnexpress.net/doi-tuyen-vn-thang-thai-lan-4876543.html",
            "crawled_at": "2026-04-20T06:00:00+07:00",
            "article_id": "a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4",
        },
        {
            "title": "Hoàng Đức giành Quả bóng Vàng 2026",
            "content": "Tiền vệ Hoàng Đức trở thành cầu thủ đầu tiên giành QBV hai năm liên tiếp kể từ Nguyễn Văn Quyết. Anh nhận 85% số phiếu từ các nhà báo.",
            "publish_date": "2026-04-18T10:00:00+07:00",
            "source": "thanhnien",
            "url": "https://thanhnien.vn/hoang-duc-qua-bong-vang-2026.htm",
            "crawled_at": "2026-04-20T06:00:00+07:00",
            "article_id": "b4d2e6f8a1c3d5e7f9b2d4e6f8a0c2d4",
        },
    ]


class TestJsonFileStoreInit:
    """Test khởi tạo JsonFileStore."""

    def test_creates_directories(self, tmp_path):
        """Init → tạo raw/, processed/, reports/ tự động."""
        store = JsonFileStore(base_dir=str(tmp_path / "storage"))
        assert (tmp_path / "storage" / "raw").exists()
        assert (tmp_path / "storage" / "processed").exists()
        assert (tmp_path / "storage" / "reports").exists()

    def test_idempotent_init(self, tmp_path):
        """Init 2 lần → không lỗi."""
        base = str(tmp_path / "storage")
        store1 = JsonFileStore(base_dir=base)
        store2 = JsonFileStore(base_dir=base)
        assert store1.raw_dir == store2.raw_dir


class TestSaveRawArticles:
    """Test save_raw_articles()."""

    def test_save_creates_json_file(self, tmp_store, sample_articles):
        """Save → file JSON tồn tại với đúng content."""
        path = tmp_store.save_raw_articles(sample_articles, source="vnexpress", date="2026-04-20")
        assert Path(path).exists()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["metadata"]["source"] == "vnexpress"
        assert data["metadata"]["total_articles"] == 2
        assert len(data["articles"]) == 2
        assert data["articles"][0]["title"] == "Đội tuyển Việt Nam thắng Thái Lan 2-1"

    def test_save_empty_list(self, tmp_store):
        """Save empty list → returns empty string."""
        path = tmp_store.save_raw_articles([], source="vnexpress", date="2026-04-20")
        assert path == ""

    def test_filename_format(self, tmp_store, sample_articles):
        """File name: {date}_{source}.json."""
        path = tmp_store.save_raw_articles(sample_articles, source="vnexpress", date="2026-04-20")
        assert "2026-04-20_vnexpress.json" in path

    def test_filename_sanitization(self, tmp_store, sample_articles):
        """Ký tự đặc biệt trong source → sanitize (Edge Case #7)."""
        path = tmp_store.save_raw_articles(sample_articles, source="vn express!@#", date="2026-04-20")
        filename = Path(path).name
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_.-" for c in filename)


class TestLoadRawArticles:
    """Test load_raw_articles()."""

    def test_load_all(self, tmp_store, sample_articles):
        """Load tất cả files."""
        tmp_store.save_raw_articles(sample_articles[:1], source="vnexpress", date="2026-04-20")
        tmp_store.save_raw_articles(sample_articles[1:], source="thanhnien", date="2026-04-20")

        all_articles = tmp_store.load_raw_articles()
        assert len(all_articles) == 2

    def test_load_by_source(self, tmp_store, sample_articles):
        """Load filter theo source."""
        tmp_store.save_raw_articles(sample_articles[:1], source="vnexpress", date="2026-04-20")
        tmp_store.save_raw_articles(sample_articles[1:], source="thanhnien", date="2026-04-20")

        vn_articles = tmp_store.load_raw_articles(source="vnexpress")
        assert len(vn_articles) == 1
        assert vn_articles[0]["source"] == "vnexpress"

    def test_load_by_date(self, tmp_store, sample_articles):
        """Load filter theo date."""
        tmp_store.save_raw_articles(sample_articles, source="vnexpress", date="2026-04-20")
        tmp_store.save_raw_articles(sample_articles, source="vnexpress", date="2026-04-19")

        today = tmp_store.load_raw_articles(date="2026-04-20")
        assert len(today) == 2

    def test_load_empty_returns_empty_list(self, tmp_store):
        """Edge Case #6: Không có file → return []."""
        articles = tmp_store.load_raw_articles()
        assert articles == []

    def test_load_corrupt_json_skipped(self, tmp_store):
        """Edge Case #2: Corrupt JSON → skip file, không crash."""
        corrupt_path = tmp_store.raw_dir / "2026-04-20_corrupt.json"
        corrupt_path.write_text("{invalid json content", encoding="utf-8")

        articles = tmp_store.load_raw_articles()
        assert articles == []


class TestSaveProcessedArticles:
    """Test save/load processed articles."""

    def test_save_and_load_processed(self, tmp_store, sample_articles):
        """Save → load processed round-trip."""
        tmp_store.save_processed_articles(sample_articles, date="2026-04-20")
        loaded = tmp_store.load_processed_articles(date="2026-04-20")
        assert len(loaded) == 2
        assert loaded[0]["title"] == sample_articles[0]["title"]

    def test_processed_metadata(self, tmp_store, sample_articles):
        """Processed file có metadata đúng."""
        path = tmp_store.save_processed_articles(sample_articles, date="2026-04-20")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["metadata"]["total_articles"] == 2
        assert "processed_at" in data["metadata"]


class TestSaveReport:
    """Test save_report()."""

    def test_save_markdown_report(self, tmp_store):
        """Save Markdown report → file tồn tại."""
        md_content = "# Test Report\n\nThis is a test."
        path = tmp_store.save_report(md_content, "weekly_report_2026-04-14_2026-04-20.md")
        assert Path(path).exists()
        assert Path(path).read_text(encoding="utf-8") == md_content

    def test_save_binary_report(self, tmp_store):
        """Save binary (PDF) report."""
        pdf_data = b"%PDF-1.4 fake pdf content"
        path = tmp_store.save_report_binary(pdf_data, "test_report.pdf")
        assert Path(path).exists()
        assert Path(path).read_bytes() == pdf_data


class TestListFiles:
    """Test list_files()."""

    def test_list_raw_files(self, tmp_store, sample_articles):
        """List files in raw directory."""
        tmp_store.save_raw_articles(sample_articles, source="vnexpress", date="2026-04-20")
        tmp_store.save_raw_articles(sample_articles, source="thanhnien", date="2026-04-20")

        files = tmp_store.list_files("raw")
        assert len(files) == 2

    def test_list_empty_directory(self, tmp_store):
        """List empty directory → []."""
        files = tmp_store.list_files("raw")
        assert files == []

    def test_list_nonexistent_directory(self, tmp_store):
        """List non-existent directory → []."""
        files = tmp_store.list_files("nonexistent")
        assert files == []
