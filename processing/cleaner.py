"""
Processing Module — cleaner.py
Data Cleaning Pipeline using Pandas according to SPEC §3.1, §3.2.
MANDATORY order: Drop Missing → Dedup → Date Filter → Normalize → Quality → Derived Columns.
"""

import html
import re
import time
import unicodedata
from datetime import datetime, timezone, timedelta

import pandas as pd

from logger import get_logger, log_function

_log = get_logger("processing.cleaner")
_VN_TZ = timezone(timedelta(hours=7))


class DataCleaner:
    """
    Pandas-based data cleaning pipeline.
    Input: list[dict] (raw articles from Storage)
    Output: pd.DataFrame (cleaned, normalized, with derived columns)
    """

    def __init__(self, days_back: int = 7):
        self.days_back = days_back
        self.cutoff_date = datetime.now(_VN_TZ) - timedelta(days=days_back)
        _log.info(
            f"DataCleaner initialized | days_back={days_back} | "
            f"cutoff_date={self.cutoff_date.isoformat()}"
        )

    @log_function("processing.cleaner")
    def clean(self, raw_articles: list[dict]) -> pd.DataFrame:
        """
        Master cleaning pipeline (SPEC §3.1).
        MANDATORY order according to SRS Business Rule #1.
        """
        start = time.perf_counter()

        # Edge Case #1: Empty raw data
        if not raw_articles:
            _log.warning("clean() called with empty input — returning empty DataFrame")
            return pd.DataFrame(columns=[
                "title", "content", "publish_date", "source", "url",
                "article_id", "content_length", "word_count", "publish_date_dt",
            ])

        df = pd.DataFrame(raw_articles)
        initial_count = len(df)

        # Step 1: Drop nulls on required fields
        df = self._drop_missing_required(df)

        # Step 2: Deduplicate by article_id
        df = self._deduplicate(df)

        # Step 3: Parse & filter dates
        df = self._filter_by_date(df)

        # Step 4: Normalize text
        df = self._normalize_text(df)

        # Step 5: Filter by content quality
        df = self._filter_quality(df)

        # Step 6: Add derived columns
        df = self._add_derived_columns(df)

        # Clean up intermediate columns
        cols_to_drop = ["publish_date_parsed", "crawled_at"]
        for col in cols_to_drop:
            if col in df.columns:
                df = df.drop(columns=[col])

        final_count = len(df)
        elapsed = round((time.perf_counter() - start) * 1000, 2)

        _log.info(
            f"Cleaning complete: {initial_count} → {final_count} articles "
            f"(removed {initial_count - final_count}) | latency={elapsed}ms"
        )

        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    #  Step 1: Drop Missing Required (SPEC §3.2)
    # ------------------------------------------------------------------

    def _drop_missing_required(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove rows missing title, content, or url."""
        start = time.perf_counter()
        before = len(df)

        required = ["title", "content", "url"]

        # Drop rows where required fields are NaN
        for col in required:
            if col in df.columns:
                df = df.dropna(subset=[col])

        # Drop rows where required fields are empty strings
        if "title" in df.columns:
            df = df[df["title"].astype(str).str.strip() != ""]
        if "content" in df.columns:
            df = df[df["content"].astype(str).str.strip() != ""]
        if "url" in df.columns:
            df = df[df["url"].astype(str).str.strip() != ""]

        after = len(df)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"Drop missing required: {before} → {after} (removed {before - after}) | latency={elapsed}ms"
        )
        return df

    # ------------------------------------------------------------------
    #  Step 2: Deduplication (SPEC §3.2)
    # ------------------------------------------------------------------

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicates based on article_id. Keep the first record."""
        start = time.perf_counter()
        before = len(df)

        if "article_id" in df.columns:
            df = df.drop_duplicates(subset=["article_id"], keep="first")
        else:
            _log.warning("Column 'article_id' not found — skipping deduplication")

        after = len(df)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"Dedup: {before} → {after} (removed {before - after}) | latency={elapsed}ms"
        )
        return df

    # ------------------------------------------------------------------
    #  Step 3: Date Filtering (SPEC §3.2)
    # ------------------------------------------------------------------

    def _filter_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep only articles within CRAWL_DAYS_BACK days. Edge Case #3, #8."""
        start = time.perf_counter()
        before = len(df)

        if "publish_date" not in df.columns:
            _log.warning("Column 'publish_date' not found — skipping date filter")
            return df

        # Parse dates (Edge Case #3: unparseable → NaT → filtered out)
        df["publish_date_parsed"] = pd.to_datetime(
            df["publish_date"],
            format="mixed",
            utc=True,
            errors="coerce",  # Return NaT if parse failure occurs
        )

        # Drop rows with NaT (unparseable dates)
        nat_count = df["publish_date_parsed"].isna().sum()
        if nat_count > 0:
            _log.warning(f"{nat_count} articles with unparseable dates will be dropped")

        df = df.dropna(subset=["publish_date_parsed"])

        # Filter: chỉ giữ bài trong cutoff range
        cutoff_utc = self.cutoff_date.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        # Edge Case #8: remove future articles
        df = df[
            (df["publish_date_parsed"] >= cutoff_utc)
            & (df["publish_date_parsed"] <= now_utc)
        ]

        after = len(df)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"Date filter ({self.days_back} days): {before} → {after} "
            f"(removed {before - after}, nat={nat_count}) | latency={elapsed}ms"
        )
        return df

    # ------------------------------------------------------------------
    #  Step 4: Text Normalization (SPEC §3.2)
    # ------------------------------------------------------------------

    def _normalize_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Chuẩn hóa text:
        - Unicode NFC normalization (Vietnamese)
        - Decode HTML entities (Edge Case #4)
        - Strip HTML tags
        - Collapse multiple whitespace
        - Strip leading/trailing whitespace
        """
        start = time.perf_counter()

        for col in ["title", "content"]:
            if col not in df.columns:
                continue

            # Edge Case #4: Decode HTML entities (&amp; &lt; etc.)
            df[col] = df[col].astype(str).apply(html.unescape)

            # Edge Case #5: Unicode NFC normalization
            df[col] = df[col].apply(lambda x: unicodedata.normalize("NFC", x))

            # Strip residual HTML tags
            df[col] = df[col].apply(lambda x: re.sub(r"<[^>]+>", "", x))

            # Collapse multiple whitespace
            df[col] = df[col].apply(lambda x: re.sub(r"\s+", " ", x))

            # Strip leading/trailing
            df[col] = df[col].str.strip()

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"Text normalization complete | latency={elapsed}ms")
        return df

    # ------------------------------------------------------------------
    #  Step 5: Content Quality Filter (SPEC §3.2)
    # ------------------------------------------------------------------

    def _filter_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove articles that are too short (< 100 content characters). SRS Rule #4."""
        start = time.perf_counter()
        before = len(df)

        if "content" in df.columns:
            df = df[df["content"].str.len() >= 100]

        after = len(df)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"Quality filter (>=100 chars): {before} → {after} "
            f"(removed {before - after}) | latency={elapsed}ms"
        )
        return df

    # ------------------------------------------------------------------
    #  Step 6: Derived Columns (SPEC §3.2)
    # ------------------------------------------------------------------

    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add content_length, word_count, publish_date_dt."""
        start = time.perf_counter()

        if "content" in df.columns:
            df["content_length"] = df["content"].str.len()
            df["word_count"] = df["content"].str.split().str.len()
        else:
            df["content_length"] = 0
            df["word_count"] = 0

        if "publish_date_parsed" in df.columns:
            df["publish_date_dt"] = df["publish_date_parsed"].dt.strftime("%Y-%m-%d")
        else:
            df["publish_date_dt"] = ""

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(f"Derived columns added | latency={elapsed}ms")
        return df
