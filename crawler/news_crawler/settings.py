"""
Crawler Module — settings.py
Scrapy settings for Parallel Crawling according to SPEC §3.3.
Reads master config from config/settings.py when available, fallback to default values.
"""

import sys
import os

# Add project root to sys.path to import config
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

BOT_NAME = "news_crawler"

SPIDER_MODULES = ["news_crawler.spiders"]
NEWSPIDER_MODULE = "news_crawler.spiders"

# --- Parallel Crawling Settings (SPEC §3.3) ---
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 30

# --- Retry (Edge Case #2, #3, #7) ---
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# --- Politeness ---
ROBOTSTXT_OBEY = True
USER_AGENT = "IntelligentSportsAssistant/1.0 (Educational Project)"

# --- Pipelines (SPEC §3.4) ---
ITEM_PIPELINES = {
    "news_crawler.pipelines.ValidationPipeline": 100,
    "news_crawler.pipelines.DateNormalizationPipeline": 200,
    "news_crawler.pipelines.DeduplicationPipeline": 300,
    "news_crawler.pipelines.JsonExportPipeline": 400,
}

# --- Output ---
FEEDS = {}  # Handled by custom JsonExportPipeline
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# --- Request Defaults ---
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

# --- AutoThrottle (Edge Case #3: 429 handling) ---
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# --- Override settings from AppSettings if available ---
try:
    from config.settings import get_settings
    _app_settings = get_settings()
    CONCURRENT_REQUESTS = _app_settings.CONCURRENT_REQUESTS
    DOWNLOAD_DELAY = _app_settings.DOWNLOAD_DELAY
    CRAWL_DAYS_BACK = _app_settings.CRAWL_DAYS_BACK
    LOG_LEVEL = "DEBUG" if _app_settings.LOG_LEVEL == "DEBUG" else "INFO"
except Exception:
    pass  # Use defaults above if config is not ready
