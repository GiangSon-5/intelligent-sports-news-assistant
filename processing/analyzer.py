"""
Processing Module — analyzer.py
Basic statistical analysis on cleaned DataFrame (SPEC §3.3).
Output: dict analysis_result matching SPEC §2.3 schema.
"""

import time

import pandas as pd

from logger import get_logger, log_function

_log = get_logger("processing.analyzer")


class DataAnalyzer:
    """
    Statistical analysis of cleaned articles.
    Output matches 100% SPEC §2.3 schema.
    """

    @log_function("processing.analyzer")
    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Statistical analysis on cleaned DataFrame.

        Args:
            df: DataFrame from DataCleaner.clean()

        Returns:
            dict matching analysis_result schema (SPEC §2.3):
                total_articles, articles_per_source, articles_per_day,
                avg_content_length, avg_word_count, date_range, source_list
        """
        start = time.perf_counter()

        # Edge Case: Empty DataFrame
        if df.empty:
            _log.warning("analyze() called with empty DataFrame — returning zero stats")
            return {
                "total_articles": 0,
                "articles_per_source": {},
                "articles_per_day": {},
                "avg_content_length": 0,
                "avg_word_count": 0,
                "date_range": {"from": "", "to": ""},
                "source_list": [],
            }

        # Total articles
        total = len(df)

        # Articles per source
        articles_per_source = {}
        if "source" in df.columns:
            articles_per_source = df["source"].value_counts().to_dict()

        # Articles per day (sorted by date ascending)
        articles_per_day = {}
        if "publish_date_dt" in df.columns:
            articles_per_day = (
                df["publish_date_dt"]
                .value_counts()
                .sort_index()
                .to_dict()
            )

        # Averages
        avg_content_length = 0
        if "content_length" in df.columns and not df["content_length"].empty:
            avg_content_length = int(df["content_length"].mean())

        avg_word_count = 0
        if "word_count" in df.columns and not df["word_count"].empty:
            avg_word_count = int(df["word_count"].mean())

        # Date range
        date_from = ""
        date_to = ""
        if "publish_date_dt" in df.columns and not df["publish_date_dt"].empty:
            date_from = str(df["publish_date_dt"].min())
            date_to = str(df["publish_date_dt"].max())

        # Source list
        source_list = []
        if "source" in df.columns:
            source_list = df["source"].unique().tolist()

        result = {
            "total_articles": total,
            "articles_per_source": articles_per_source,
            "articles_per_day": articles_per_day,
            "avg_content_length": avg_content_length,
            "avg_word_count": avg_word_count,
            "date_range": {
                "from": date_from,
                "to": date_to,
            },
            "source_list": source_list,
        }

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _log.info(
            f"Analysis complete | total={total} | sources={source_list} | "
            f"date_range={date_from}→{date_to} | avg_len={avg_content_length} | "
            f"latency={elapsed}ms"
        )

        return result
