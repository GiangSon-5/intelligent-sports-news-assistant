"""
Crawler Module — middlewares.py
Custom Scrapy middlewares for resilience & logging.
"""

import logging
import random

from scrapy import signals
from scrapy.http import Request, Response

logger = logging.getLogger("sports_assistant.crawler.middleware")


class RotatingUserAgentMiddleware:
    """
    Rotate User-Agent header to reduce the risk of being blocked (Edge Case #2).
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "IntelligentSportsAssistant/1.0 (Educational Project)",
    ]

    def process_request(self, request: Request, spider) -> None:
        request.headers["User-Agent"] = random.choice(self.USER_AGENTS)


class CrawlStatsMiddleware:
    """
    Middleware to record crawl statistics for each spider.
    """

    def __init__(self):
        self.stats = {}

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def spider_opened(self, spider) -> None:
        self.stats[spider.name] = {
            "requests_made": 0,
            "responses_received": 0,
            "errors": 0,
        }
        logger.info(f"Spider opened: {spider.name}")

    def spider_closed(self, spider, reason: str) -> None:
        stats = self.stats.get(spider.name, {})
        logger.info(
            f"Spider closed: {spider.name} | reason={reason} | "
            f"requests={stats.get('requests_made', 0)} | "
            f"responses={stats.get('responses_received', 0)} | "
            f"errors={stats.get('errors', 0)}"
        )

    def process_request(self, request: Request, spider) -> None:
        if spider.name in self.stats:
            self.stats[spider.name]["requests_made"] += 1

    def process_response(self, request: Request, response: Response, spider) -> Response:
        if spider.name in self.stats:
            self.stats[spider.name]["responses_received"] += 1

        if response.status in (403, 429):
            logger.warning(
                f"HTTP {response.status} from {response.url} (spider={spider.name})"
            )

        return response

    def process_exception(self, request: Request, exception, spider) -> None:
        if spider.name in self.stats:
            self.stats[spider.name]["errors"] += 1
        logger.error(
            f"Request exception: {type(exception).__name__}: {exception} | url={request.url}"
        )
