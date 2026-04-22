"""
Crawler Module — pipelines.py
Scrapy Item Pipelines according to SPEC §3.4:
  1. ValidationPipeline     (prio 100): Check required fields
  2. DateNormalizationPipeline (prio 200): Parse Vietnamese date → ISO 8601
  3. DeduplicationPipeline  (prio 300): Remove duplicate SHA256(url)
  4. JsonExportPipeline     (prio 400): Write JSON → storage/raw/
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from scrapy.exceptions import DropItem

logger = logging.getLogger("sports_assistant.crawler.pipeline")

_VN_TZ = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
#  Pipeline 1: Validation (prio 100) — SPEC §3.4, Edge Case #4, #10
# ---------------------------------------------------------------------------

class ValidationPipeline:
    """
    Check if item has all required fields.
    Drop item if title, content, or url is missing.
    Edge Case #4: Video-only → empty content → drop.
    Edge Case #10: Paywall → content < 100 chars → drop.
    """

    def process_item(self, item, spider):
        start = time.perf_counter()

        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        if not title or not str(title).strip():
            logger.warning(f"Validation FAIL: missing title | url={url}")
            raise DropItem(f"Missing title: {url}")

        if not content or not str(content).strip():
            logger.warning(f"Validation FAIL: missing content | url={url}")
            raise DropItem(f"Missing content (video-only?): {url}")

        if len(str(content).strip()) < 100:
            logger.warning(f"Validation FAIL: content too short ({len(content)} chars) | url={url}")
            raise DropItem(f"Content too short (<100 chars, paywall?): {url}")

        if not url or not str(url).strip():
            logger.warning(f"Validation FAIL: missing url")
            raise DropItem("Missing URL")

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"Validation OK | title='{title[:50]}...' | latency={elapsed}ms")

        return item


# ---------------------------------------------------------------------------
#  Pipeline 2: Date Normalization (prio 200) — SPEC §3.4, Edge Case #5
# ---------------------------------------------------------------------------

class DateNormalizationPipeline:
    """
    Normalize publish_date to ISO 8601 (+07:00).
    Supports parsing multiple Vietnamese date formats.
    Edge Case #5: Format not recognized → fallback to crawled_at.
    """

    # Vietnamese month names for manual parsing
    _VIET_MONTHS = {
        "1": 1, "01": 1, "2": 2, "02": 2, "3": 3, "03": 3,
        "4": 4, "04": 4, "5": 5, "05": 5, "6": 6, "06": 6,
        "7": 7, "07": 7, "8": 8, "08": 8, "9": 9, "09": 9,
        "10": 10, "11": 11, "12": 12,
    }

    def process_item(self, item, spider):
        start = time.perf_counter()

        raw_date = str(item.get("publish_date", "")).strip()
        parsed = self._parse_vietnamese_date(raw_date)

        if not parsed:
            # Data Integrity: DO NOT arbitrarily assign today's date if failure occurs
            # Leave the original value or None so the user knows
            parsed = None
            logger.warning(
                f"[{spider.name.upper()}] Date Parse FAILURE | "
                "Reason: No matching pattern found | "
                f"Raw String: '{raw_date}' | "
                f"URL: {item.get('url', '')}"
            )
        
        item["publish_date"] = parsed

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        if parsed:
            logger.debug(f"DateNormalization OK | '{raw_date}' → '{parsed}' | latency={elapsed}ms")

        return item

    def _parse_vietnamese_date(self, raw: str) -> Optional[str]:
        """
        Comprehensive time filter (Exhaustive Parser):
        Supports multiple formats from Vietnamese press, including strange separator characters.
        """
        if not raw:
            return None

        # 0. Is it already ISO 8601 (from meta tags)?
        if re.match(r"^\d{4}-\d{2}-\d{2}T", raw):
            return raw

        # Pre-processing: remove noise characters, normalize whitespace
        clean_raw = re.sub(r"\s+", " ", raw).strip()

        # 1. Pattern: dd/mm/yyyy HH:MM (and variants using -, . separators)
        # Example: 14/04/2026 20:30, 14-04-2026, 14.04.2026
        match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})[\s,]*(\d{1,2}):(\d{2})", clean_raw)
        if match:
            day, month, year, hour, minute = [int(x) for x in match.groups()]
            return self._to_iso(year, month, day, hour, minute)

        # 2. Pattern: HH:MM dd/mm/yyyy (Reversed)
        match = re.search(r"(\d{1,2}):(\d{2})[\s,]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", clean_raw)
        if match:
            hour, minute, day, month, year = [int(x) for x in match.groups()]
            return self._to_iso(year, month, day, hour, minute)

        # 3. Pattern: dd/mm/yyyy (Date only)
        match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", clean_raw)
        if match:
            day, month, year = [int(x) for x in match.groups()]
            return self._to_iso(year, month, day)

        # 4. Pattern: Shortened year dd/mm/yy (e.g., 14/04/26)
        match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2})\s+(\d{1,2}):(\d{2})", clean_raw)
        if match:
            day, month, year_short, hour, minute = [int(x) for x in match.groups()]
            year = 2000 + year_short if year_short < 50 else 1900 + year_short
            return self._to_iso(year, month, day, hour, minute)

        # 5. Pattern: Contains the word "Tháng" (Month) (e.g., 14 Tháng 4, 2026)
        match = re.search(r"(\d{1,2})\s+Tháng\s+(\d{1,2})[\s,]+(\d{4})", clean_raw, re.IGNORECASE)
        if match:
            day, month, year = [int(x) for x in match.groups()]
            return self._to_iso(year, month, day)

        # 6. Pattern: Relative time (X hours/minutes ago)
        match = re.search(r"(\d+)\s*(giờ|phút|ngày|tuần)\s*trước", clean_raw, re.IGNORECASE)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            now = datetime.now(_VN_TZ)
            if "phút" in unit: dt = now - timedelta(minutes=amount)
            elif "giờ" in unit: dt = now - timedelta(hours=amount)
            elif "ngày" in unit: dt = now - timedelta(days=amount)
            elif "tuần" in unit: dt = now - timedelta(weeks=amount)
            else: return None
            return dt.isoformat()

        return None

    def _to_iso(self, year, month, day, hour=0, minute=0) -> Optional[str]:
        """Helper to safely convert to ISO string."""
        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=_VN_TZ)
            return dt.isoformat()
        except ValueError:
            return None


# ---------------------------------------------------------------------------
#  Pipeline 3: Deduplication (prio 300) — SPEC §3.4, Edge Case #6
# ---------------------------------------------------------------------------

class DeduplicationPipeline:
    """
    Remove duplicate articles based on article_id (SHA256 of URL).
    Keep the first record encountered.
    """

    def __init__(self):
        self.seen_ids: set[str] = set()

    def process_item(self, item, spider):
        start = time.perf_counter()

        article_id = item.get("article_id", "")

        if not article_id:
            # Generate if not already present
            url = item.get("url", "")
            article_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
            item["article_id"] = article_id

        if article_id in self.seen_ids:
            logger.info(f"Dedup DROP: duplicate article_id={article_id[:16]}... | url={item.get('url', '')}")
            raise DropItem(f"Duplicate: {item.get('url', '')}")

        self.seen_ids.add(article_id)

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"Dedup OK | id={article_id[:16]}... | latency={elapsed}ms")

        return item


# ---------------------------------------------------------------------------
#  Pipeline 4: JSON Export (prio 400) — SPEC §3.4
# ---------------------------------------------------------------------------

class JsonExportPipeline:
    """
    Collect articles by spider name, write JSON to storage/raw/ when spider closes.
    File format: {date}_{spider_name}.json
    """

    def __init__(self):
        self._items: dict[str, list[dict]] = {}  # spider_name → list of items

    def open_spider(self, spider) -> None:
        self._items[spider.name] = []
        logger.info(f"JsonExportPipeline opened for spider: {spider.name}")

    def process_item(self, item, spider):
        start = time.perf_counter()

        article_dict = dict(item)
        self._items.setdefault(spider.name, []).append(article_dict)

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        count = len(self._items[spider.name])
        logger.debug(f"JsonExport collected #{count} | spider={spider.name} | latency={elapsed}ms")

        return item

    def close_spider(self, spider) -> None:
        """Write all items to JSON when the spider closes."""
        start = time.perf_counter()

        items = self._items.get(spider.name, [])
        if not items:
            logger.warning(f"JsonExportPipeline: No items to export for spider={spider.name}")
            return

        today = datetime.now(_VN_TZ).strftime("%Y-%m-%d")

        # Use Storage module if available, fallback to direct write
        try:
            import sys
            import os
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            from storage.json_store import JsonFileStore
            store = JsonFileStore(base_dir=os.path.join(project_root, "storage"))
            filepath = store.save_raw_articles(items, source=spider.name, date=today)
        except Exception as e:
            # Fallback: direct JSON write
            logger.warning(f"Storage module unavailable, using direct write: {e}")
            filepath = self._direct_write(items, spider.name, today)

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"JsonExport DONE | spider={spider.name} | "
            f"articles={len(items)} | file={filepath} | latency={elapsed}ms"
        )

    def _direct_write(self, items: list[dict], spider_name: str, date: str) -> str:
        """Fallback: write JSON directly when Storage module is not available."""
        import os
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        raw_dir = Path(project_root) / "storage" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        filepath = raw_dir / f"{date}_{spider_name}.json"

        data = {
            "metadata": {
                "source": spider_name,
                "crawled_at": datetime.now(_VN_TZ).isoformat(),
                "total_articles": len(items),
            },
            "articles": items,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return str(filepath)
