"""
Storage Module — json_store.py
Abstraction layer for JSON file-based storage.
Implements Repository Pattern according to SPEC: atomic writes, filtering, metadata envelope.
Designed to be easily extended to SQLite/PostgreSQL via ArticleStore Protocol.
"""

import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from logger import get_logger, log_function

_log = get_logger("storage")

_VN_TZ = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
#  Custom Exception
# ---------------------------------------------------------------------------

class StorageError(Exception):
    """Error related to storage operations."""
    pass


# ---------------------------------------------------------------------------
#  Protocol / Interface (SPEC §2.1)
# ---------------------------------------------------------------------------

@runtime_checkable
class ArticleStore(Protocol):
    """Interface for storage backend — JSON or DB."""

    def save_raw_articles(self, articles: list[dict], source: str, date: str) -> str: ...

    def load_raw_articles(self, source: str | None = None, date: str | None = None) -> list[dict]: ...

    def save_processed_articles(self, articles: list[dict], date: str) -> str: ...

    def load_processed_articles(self, date: str | None = None) -> list[dict]: ...

    def save_ai_result(self, result: dict, date: str) -> str: ...

    def load_ai_result(self, date: str | None = None) -> dict | None: ...

    def save_report(self, content: str, filename: str) -> str: ...

    def list_files(self, directory: str, pattern: str = "*.json") -> list[str]: ...


# ---------------------------------------------------------------------------
#  JSON File Store — Concrete Implementation (SPEC §2.2)
# ---------------------------------------------------------------------------

class JsonFileStore:
    """
    Concrete implementation — JSON file-based storage.
    Implements ArticleStore Protocol.
    """

    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "raw"
        self.processed_dir = self.base_dir / "processed"
        self.ai_results_dir = self.base_dir / "ai_results"
        self.reports_dir = self.base_dir / "reports"

        # Ensure directories exist (Edge Case #3: permission check)
        for d in [self.raw_dir, self.processed_dir, self.ai_results_dir, self.reports_dir]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise StorageError(f"Cannot write to {d}. Check directory permissions.")

        _log.info(
            "JsonFileStore initialized",
            extra={
                "details": {
                    "base_dir": str(self.base_dir.resolve()),
                    "raw_dir": str(self.raw_dir),
                    "processed_dir": str(self.processed_dir),
                    "ai_results_dir": str(self.ai_results_dir),
                    "reports_dir": str(self.reports_dir),
                }
            },
        )

    # ------------------------------------------------------------------
    #  Atomic Write (SPEC §3.1)
    # ------------------------------------------------------------------

    def _atomic_write_json(self, filepath: Path, data: dict) -> None:
        """
        Write JSON via temp file + atomic rename.
        Avoid data corruption if the process crashes midway.
        Edge Case #1: Disk full → delete temp file → raise StorageError.
        """
        temp_fd = None
        temp_path = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(
                dir=str(filepath.parent),
                suffix=".tmp",
            )
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_fd = None  # fd already closed by context manager

            # Atomic rename (same filesystem)
            Path(temp_path).replace(filepath)
            _log.debug(f"Atomic write successful: {filepath}")
        except Exception as e:
            if temp_path and Path(temp_path).exists():
                try:
                    Path(temp_path).unlink()
                except OSError:
                    pass
            raise StorageError(f"Failed to write {filepath}: {e}") from e

    # ------------------------------------------------------------------
    #  Filename Sanitization (Edge Case #7)
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Only allow [a-z0-9_-.] in filename."""
        sanitized = re.sub(r"[^a-z0-9_.\-]", "_", name.lower())
        return sanitized

    # ------------------------------------------------------------------
    #  RAW Articles (SPEC §2.3, §2.4)
    # ------------------------------------------------------------------

    @log_function("storage")
    def save_raw_articles(self, articles: list[dict], source: str, date: str) -> str:
        """
        Save raw articles to storage/raw/{date}_{source}.json.
        Perform SMART MERGE: If file already exists, automatically merge and detect changes.
        """
        if not articles:
            _log.warning(f"save_raw_articles called with empty list for source={source}")
            return ""

        safe_source = self._sanitize_filename(source)
        safe_date = self._sanitize_filename(date)
        filename = f"{safe_date}_{safe_source}.json"
        filepath = self.raw_dir / filename

        # 1. Load existing data if any (for Merging)
        existing_map = {}
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    for art in old_data.get("articles", []):
                        if "article_id" in art:
                            existing_map[art["article_id"]] = art
            except Exception as e:
                _log.warning(f"Could not load existing file for merge: {e}. Overwriting instead.")

        # 2. Perform Smart Merge & Change Detection
        merged_articles = existing_map.copy()
        new_count = 0
        update_count = 0
        
        now_iso = datetime.now(_VN_TZ).isoformat()

        for new_art in articles:
            art_id = new_art.get("article_id")
            if not art_id:
                continue
            
            if art_id in existing_map:
                # EXISTING ARTICLE - Checking for changes
                old_art = existing_map[art_id]
                
                old_t_hash = old_art.get("title_hash")
                old_c_hash = old_art.get("content_hash")
                new_t_hash = new_art.get("title_hash")
                new_c_hash = new_art.get("content_hash")
                
                title_changed = new_t_hash != old_t_hash
                content_changed = new_c_hash != old_c_hash
                
                if title_changed or content_changed:
                    # CHANGE DETECTED
                    update_type = "both" if (title_changed and content_changed) else ("title" if title_changed else "content")
                    
                    # Updating article information
                    old_art.update(new_art) # Overwriting with new content
                    old_art["version"] = old_art.get("version", 1) + 1
                    old_art["update_type"] = update_type
                    old_art["last_updated_at"] = now_iso
                    
                    update_count += 1
                    msg = f"[UPDATE] {update_type.upper()} changed | url={new_art.get('url')}"
                    _log.info(msg)
                else:
                    # No change -> skip (keep old version to preserve original crawled_at)
                    pass
            else:
                # COMPLETELY NEW ARTICLE
                new_art["version"] = 1
                new_art["update_type"] = "new"
                new_art["last_updated_at"] = now_iso
                merged_articles[art_id] = new_art
                new_count += 1

        # 3. Build metadata envelope
        final_list = list(merged_articles.values())
        data = {
            "metadata": {
                "source": source,
                "crawled_at": now_iso,
                "total_articles": len(final_list),
                "stats": {
                    "new": new_count,
                    "updated": update_count,
                    "deduped": len(articles) - new_count - update_count
                },
                "date_range": {"from": date, "to": date},
            },
            "articles": final_list,
        }

        self._atomic_write_json(filepath, data)

        _log.info(
            f"Smart Merge DONE | spider={source} | total={len(final_list)} | new={new_count} | updated={update_count}",
            extra={
                "details": {
                    "filepath": str(filepath),
                    "new": new_count,
                    "updated": update_count,
                }
            },
        )

        return str(filepath)

    @log_function("storage")
    def load_raw_articles(
        self,
        source: str | None = None,
        date: str | None = None,
    ) -> list[dict]:
        """
        Load raw articles with optional filtering (SPEC §3.2).
        Edge Case #2: corrupt JSON → skip file.
        Edge Case #6: no files → return [].
        """
        pattern = "*.json"
        if source and date:
            pattern = f"{self._sanitize_filename(date)}_{self._sanitize_filename(source)}.json"
        elif source:
            pattern = f"*_{self._sanitize_filename(source)}.json"
        elif date:
            pattern = f"{self._sanitize_filename(date)}_*.json"

        articles: list[dict] = []
        files_read = 0
        files_skipped = 0

        for filepath in sorted(self.raw_dir.glob(pattern)):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    articles.extend(data.get("articles", []))
                    files_read += 1
            except json.JSONDecodeError as e:
                _log.warning(
                    f"Corrupt JSON file skipped: {filepath}",
                    extra={"error": {"type": "JSONDecodeError", "message": str(e)}},
                )
                files_skipped += 1
            except Exception as e:
                _log.error(
                    f"Error reading {filepath}",
                    extra={"error": {"type": type(e).__name__, "message": str(e)}},
                )
                files_skipped += 1

        _log.info(
            f"Loaded {len(articles)} raw articles from {files_read} files (skipped {files_skipped})",
        )

        return articles

    # ------------------------------------------------------------------
    #  PROCESSED Articles
    # ------------------------------------------------------------------

    @log_function("storage")
    def save_processed_articles(self, articles: list[dict], date: str) -> str:
        """
        Save processed articles to storage/processed/{date}_processed.json.
        """
        safe_date = self._sanitize_filename(date)
        filename = f"{safe_date}_processed.json"
        filepath = self.processed_dir / filename

        now_iso = datetime.now(_VN_TZ).isoformat()

        # Collect unique sources
        sources = list({a.get("source", "unknown") for a in articles})

        data = {
            "metadata": {
                "processed_at": now_iso,
                "total_articles": len(articles),
                "sources": sorted(sources),
            },
            "articles": articles,
        }

        self._atomic_write_json(filepath, data)

        _log.info(
            f"Saved {len(articles)} processed articles to {filepath}",
        )

        return str(filepath)

    @log_function("storage")
    def load_processed_articles(self, date: str | None = None) -> list[dict]:
        """Load processed articles."""
        if date:
            pattern = f"{self._sanitize_filename(date)}_processed.json"
        else:
            pattern = "*_processed.json"

        articles: list[dict] = []
        for filepath in sorted(self.processed_dir.glob(pattern)):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    articles.extend(data.get("articles", []))
            except json.JSONDecodeError as e:
                _log.warning(
                    f"Corrupt processed JSON skipped: {filepath}",
                    extra={"error": {"type": "JSONDecodeError", "message": str(e)}},
                )
            except Exception as e:
                _log.error(
                    f"Error reading processed file {filepath}",
                    extra={"error": {"type": type(e).__name__, "message": str(e)}},
                )

        _log.info(f"Loaded {len(articles)} processed articles")
        return articles

    # ------------------------------------------------------------------
    #  AI RESULTS
    # ------------------------------------------------------------------

    @log_function("storage")
    def save_ai_result(self, result: dict, date: str) -> str:
        """
        Save AI results to storage/ai_results/{date}_ai_result.json.
        """
        safe_date = self._sanitize_filename(date)
        filename = f"{safe_date}_ai_result.json"
        filepath = self.ai_results_dir / filename

        self._atomic_write_json(filepath, result)

        _log.info(f"Saved AI result to {filepath}")
        return str(filepath)

    @log_function("storage")
    def load_ai_result(self, date: str | None = None) -> dict | None:
        """Load AI results."""
        if date:
            pattern = f"{self._sanitize_filename(date)}_ai_result.json"
        else:
            pattern = "*_ai_result.json"

        # Load the latest file (based on sorted file names)
        files = sorted(self.ai_results_dir.glob(pattern), reverse=True)
        if not files:
            _log.warning("No AI result file found")
            return None

        filepath = files[0]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                _log.info(f"Loaded AI result from {filepath}")
                return data
        except json.JSONDecodeError as e:
            _log.warning(f"Corrupt AI result JSON skipped: {filepath}", extra={"error": str(e)})
        except Exception as e:
            _log.error(f"Error reading AI result file {filepath}", extra={"error": str(e)})

        return None

    # ------------------------------------------------------------------
    #  REPORTS
    # ------------------------------------------------------------------

    @log_function("storage")
    def save_report(self, content: str, filename: str) -> str:
        """
        Save report (Markdown or text) to storage/reports/.
        Return file path.
        """
        # Cho phép dấu chấm trong filename (ví dụ .md, .pdf)
        safe_name = re.sub(r"[^a-zA-Z0-9_.\-]", "_", filename)
        filepath = self.reports_dir / safe_name

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            _log.info(f"Report saved: {filepath} ({len(content)} chars)")
        except Exception as e:
            raise StorageError(f"Failed to save report {filepath}: {e}") from e

        return str(filepath)

    def save_report_binary(self, data: bytes, filename: str) -> str:
        """Save report in binary format (PDF)."""
        safe_name = re.sub(r"[^a-zA-Z0-9_.\-]", "_", filename)
        filepath = self.reports_dir / safe_name

        try:
            with open(filepath, "wb") as f:
                f.write(data)
            _log.info(f"Binary report saved: {filepath} ({len(data)} bytes)")
        except Exception as e:
            raise StorageError(f"Failed to save binary report {filepath}: {e}") from e

        return str(filepath)

    # ------------------------------------------------------------------
    #  UTILITY
    # ------------------------------------------------------------------

    @log_function("storage")
    def list_files(self, directory: str, pattern: str = "*.json") -> list[str]:
        """List files in directory matching pattern."""
        dir_map = {
            "raw": self.raw_dir,
            "processed": self.processed_dir,
            "ai_results": self.ai_results_dir,
            "reports": self.reports_dir,
        }
        target_dir = dir_map.get(directory, Path(directory))

        if not target_dir.exists():
            _log.warning(f"Directory not found: {target_dir}")
            return []

        files = sorted(str(f) for f in target_dir.glob(pattern))
        _log.debug(f"Listed {len(files)} files in {target_dir} matching {pattern}")
        return files
