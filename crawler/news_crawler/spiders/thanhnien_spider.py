"""
Spider: Thanh Niên — https://thanhnien.vn/the-thao
2-phase crawling: listing page → detail page.
Selectors according to SPEC §3.2.
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timezone, timedelta

import scrapy

from news_crawler.items import NewsArticleItem

logger = logging.getLogger("sports_assistant.crawler.thanhnien")
_VN_TZ = timezone(timedelta(hours=7))
_MAX_PAGES = 10


class ThanhnienSpider(scrapy.Spider):
    name = "thanhnien"
    allowed_domains = ["thanhnien.vn"]
    start_urls = []
    category_id = "185318"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_count = 1
        self._article_count = 0
        self._start_time = time.perf_counter()
        self.stop_date = None # Will be set in start_requests

    def start_requests(self):
        # Dynamic crawl range from settings (defaults to 7 if not set)
        days_to_crawl = self.settings.getint("CRAWL_DAYS_BACK", 7)
        self.stop_date = datetime.now(_VN_TZ) - timedelta(days=days_to_crawl)
        logger.info(f"Spider started | stop_date={self.stop_date.strftime('%Y-%m-%d')} ({days_to_crawl} days)")

        url = f"https://thanhnien.vn/timelinelist/{self.category_id}/{self._page_count}.htm"
        yield scrapy.Request(url, callback=self.parse)

    # ------------------------------------------------------------------
    #  Phase 1: LIST PAGE (API Based)
    # ------------------------------------------------------------------

    def parse(self, response):
        start = time.perf_counter()
        
        # API returns HTML fragment
        items = response.xpath("//div[contains(@class, 'box-category-item')]")
        if not items:
            logger.warning(f"No items found on API page {self._page_count}")
            return

        stop_crawling = False
        articles_on_page = 0
        
        for item in items:
            url = response.urljoin(item.xpath(".//a[contains(@class, 'box-category-link-title')]/@href").get())
            raw_date = item.xpath(".//*[@title]/@title").get()
            
            try:
                # Robust cleaning before parsing (similar to Pipeline)
                clean_date = re.sub(r"(Thứ\s+[a-z0-9]+|Chủ\s+nhật|T[2-7]|CN)[\s,]*", "", raw_date, flags=re.IGNORECASE)
                clean_date = re.sub(r"\(?GMT[+-]\d+\)?", "", clean_date).strip()
                
                # Format: "15:30 05/05/2026" or "05/05/2026 15:30"
                match = re.search(r"(\d{1,2}):(\d{2})\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", clean_date)
                if match:
                    h, m, d, mo, y = [int(x) for x in match.groups()]
                    dt = datetime(y, mo, d, h, m, tzinfo=_VN_TZ)
                else:
                    # Try reverse format
                    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s+(\d{1,2}):(\d{2})", clean_date)
                    if match:
                        d, mo, y, h, m = [int(x) for x in match.groups()]
                        dt = datetime(y, mo, d, h, m, tzinfo=_VN_TZ)
                    else:
                        raise ValueError("No recognizable date pattern")

                if dt < self.stop_date:
                    stop_crawling = True
                    logger.info(f"Reached stop date {self.stop_date}. Stopping crawl.")
                    break
            except Exception as e:
                logger.warning(f"Spider Date Check Failed | Raw: '{raw_date}' | Error: {e}")

            articles_on_page += 1
            yield scrapy.Request(
                url=url,
                callback=self.parse_article,
                errback=self.handle_error,
                meta={'publish_date': raw_date}
            )

        logger.info(f"Found {articles_on_page} articles on API page {self._page_count}")

        # Pagination
        if not stop_crawling and self._page_count < 100:
            self._page_count += 1
            next_url = f"https://thanhnien.vn/timelinelist/{self.category_id}/{self._page_count}.htm"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                errback=self.handle_error
            )

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"Listing parse done | url={response.url} | latency={elapsed}ms")

    # ------------------------------------------------------------------
    #  Phase 2: DETAIL PAGE
    # ------------------------------------------------------------------

    def parse_article(self, response):
        start = time.perf_counter()

        # Title
        title = response.css("h1.detail-title [data-role='title']::text").get()
        if not title:
            title = response.css("h1.detail-title *::text").get()
        if not title:
            title = response.css("h1::text").get()
            
        if not title or not title.strip():
            logger.warning(f"Failed to extract title from {response.url}")
            return

        title = title.strip()

        # Content
        paragraphs = response.css("div.detail-content p *::text").getall()
        if not paragraphs:
            paragraphs = response.css("div.detail-content *::text").getall()
            
        content = " ".join(p.strip() for p in paragraphs if p.strip())
        
        # Date (Prefer date from meta if available, else from page)
        raw_date = response.meta.get('publish_date')
        if not raw_date:
            raw_date = response.css("meta[property='article:published_time']::attr(content)").get()
        if not raw_date:
            raw_date = response.css("div.detail-time span::text").get()
        raw_date = (raw_date or "").strip()

        if not content or len(content) < 100:
            logger.warning(f"Content too short ({len(content)} chars) from {response.url}")
            return

        # Stable ID Mapping
        canonical_url = response.css("link[rel='canonical']::attr(href)").get() or response.url
        article_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        
        # Fingerprinting
        title_hash = hashlib.sha256(title.encode("utf-8")).hexdigest()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        now = datetime.now(_VN_TZ).isoformat()

        self._article_count += 1

        item = NewsArticleItem(
            title=title,
            content=content,
            publish_date=raw_date,
            source="thanhnien",
            url=response.url,
            crawled_at=now,
            article_id=article_id,
            title_hash=title_hash,
            content_hash=content_hash,
            version=1,
            update_type="new",
            last_updated_at=now,
        )

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"Article #{self._article_count} parsed | title='{title[:40]}...' | latency={elapsed}ms")

        yield item

    def handle_error(self, failure):
        logger.error(f"Request failed | url={failure.request.url} | error={failure.type.__name__}: {failure.value}")

    def closed(self, reason):
        elapsed = round(time.perf_counter() - self._start_time, 1)
        logger.info(f"Thanh Nien spider closed | reason={reason} | pages={self._page_count} | articles={self._article_count} | duration={elapsed}s")
