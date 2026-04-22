"""
Crawler Module — run.py
Entry point to run all spiders concurrently (Parallel Crawling).
Use Scrapy CrawlerProcess with Twisted reactor (SPEC §3.5).
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

_VN_TZ = timezone(timedelta(hours=7))

# Ensure project root is in sys.path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_crawler_root = os.path.abspath(os.path.dirname(__file__))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

logger = logging.getLogger("sports_assistant.crawler.run")


def run_all_spiders(settings=None) -> dict:
    """
    Run all 3 spiders concurrently via CrawlerProcess.
    
    Args:
        settings: AppSettings instance (optional). If None, use Scrapy defaults.
    
    Returns:
        dict: Crawl result summary.
            {
                "total_articles": int,
                "sources_completed": list[str],
                "sources_failed": list[str],
                "duration_seconds": float,
            }
    """
    start_time = time.perf_counter()
    logger.info("Starting parallel crawl — 3 spiders")

    # Import Scrapy components
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    # Load Scrapy settings
    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "news_crawler.settings")

    scrapy_settings = get_project_settings()

    # Override from AppSettings if available
    if settings:
        scrapy_settings.set("CONCURRENT_REQUESTS", settings.CONCURRENT_REQUESTS)
        scrapy_settings.set("DOWNLOAD_DELAY", settings.DOWNLOAD_DELAY)
        if settings.LOG_LEVEL == "DEBUG":
            scrapy_settings.set("LOG_LEVEL", "DEBUG")

    sources_completed = []
    sources_failed = []

    try:
        process = CrawlerProcess(scrapy_settings)

        # Import spider classes
        from news_crawler.spiders.vnexpress_spider import VnexpressSpider
        from news_crawler.spiders.thanhnien_spider import ThanhnienSpider
        from news_crawler.spiders.tuoitre_spider import TuoitreSpider

        # Queue all 3 spiders
        process.crawl(VnexpressSpider)
        process.crawl(ThanhnienSpider)
        process.crawl(TuoitreSpider)

        # Block until all spiders finish (Twisted reactor)
        process.start()

        sources_completed = ["vnexpress", "thanhnien", "tuoitre"]
        logger.info(f"All spiders completed successfully")

    except Exception as e:
        logger.error(f"Crawler process error: {type(e).__name__}: {e}")
        # If a part has run, it's partial success
        if not sources_completed:
            sources_failed = ["vnexpress", "thanhnien", "tuoitre"]

    duration = round(time.perf_counter() - start_time, 1)

    # Count articles from storage
    total_articles = 0
    try:
        from storage.json_store import JsonFileStore
        store = JsonFileStore(base_dir=os.path.join(_project_root, "storage"))
        today = datetime.now(_VN_TZ).strftime("%Y-%m-%d")
        articles = store.load_raw_articles(date=today)
        total_articles = len(articles)
    except Exception as e:
        logger.warning(f"Could not count articles from storage: {e}")

    result = {
        "total_articles": total_articles,
        "sources_completed": sources_completed,
        "sources_failed": sources_failed,
        "duration_seconds": duration,
    }

    logger.info(
        f"Crawl finished | articles={total_articles} | "
        f"completed={sources_completed} | failed={sources_failed} | "
        f"duration={duration}s"
    )

    return result
