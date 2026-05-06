"""
Spider: Tuổi Trẻ — https://tuoitre.vn/the-thao.htm
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

logger = logging.getLogger("sports_assistant.crawler.tuoitre")
_VN_TZ = timezone(timedelta(hours=7))
_MAX_PAGES = 10


class TuoitreSpider(scrapy.Spider):
    name = "tuoitre"
    allowed_domains = ["tuoitre.vn"]
    start_urls = []
    category_id = "1209" # Sports category ID

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

        url = f"https://tuoitre.vn/timeline/{self.category_id}/trang-{self._page_count}.htm"
        yield scrapy.Request(url, callback=self.parse)

    # ------------------------------------------------------------------
    #  Phase 1: LIST PAGE (API Based)
    # ------------------------------------------------------------------

    def parse(self, response):
        start = time.perf_counter()
        
        # API returns HTML fragment. Each item is a <li>
        items = response.xpath("//li[contains(@class, 'news-item')]")
        if not items:
            logger.warning(f"No items found on API page {self._page_count}")
            return

        stop_crawling = False
        articles_on_page = 0
        
        for item in items:
            url = response.urljoin(item.xpath(".//a[contains(@class, 'box-category-link-title')]/@href").get())
            # Note: Tuoi Tre API fragment often doesn't have a visible date string in the listing, 
            # or it's in a format we might need to fetch from the detail page.
            # However, we can use the order of articles and check the date in parse_article.
            
            articles_on_page += 1
            yield scrapy.Request(
                url=url,
                callback=self.parse_article,
                errback=self.handle_error
            )

        logger.info(f"Found {articles_on_page} articles on API page {self._page_count}")

        # Pagination: Continue until max pages or we find an article older than stop_date
        # Since we don't have the date in the listing, we rely on the detail page to stop.
        # However, for simplicity and performance, we'll keep the page limit.
        if self._page_count < 50: 
            self._page_count += 1
            next_url = f"https://tuoitre.vn/timeline/{self.category_id}/trang-{self._page_count}.htm"
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

        # Date Check (Exhaustive & Accurate)
        raw_date = response.css("div.detail-time [data-role='publishdate']::text").get()
        if not raw_date:
            raw_date = response.css("meta[property='article:published_time']::attr(content)").get()
        if not raw_date:
            raw_date = response.css("span.detail-time::text").get()
        
        raw_date = (raw_date or "").strip()
        
        # --- NEW: Early Stopping Logic ---
        try:
            # Clean: "06/05/2026 12:30"
            clean_date = re.sub(r"(Thứ\s+[a-z0-9]+|Chủ\s+nhật|T[2-7]|CN)[\s,]*", "", raw_date, flags=re.IGNORECASE)
            match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})[\s,]*(\d{1,2}):(\d{2})", clean_date)
            if match:
                d, mo, y, h, m = [int(x) for x in match.groups()]
                dt = datetime(y, mo, d, h, m, tzinfo=_VN_TZ)
                if dt < self.stop_date:
                    logger.info(f"Article is older than stop_date ({dt} < {self.stop_date}). Skipping.")
                    return # Do not yield this item
        except Exception as e:
            logger.debug(f"Date check failed on detail page: {e}")

        # Title
        title = response.css("h1.detail-title::text").get()
        if not title:
            title = response.css("h1.article-title::text").get()
        if not title:
            title = response.css("h1::text").get()
            
        if not title or not title.strip():
            logger.warning(f"Failed to extract title from {response.url}")
            return

        title = title.strip()

        # Content
        paragraphs = response.css("div.detail-content p::text").getall()
        if not paragraphs:
            paragraphs = response.css("div.detail-content p *::text").getall()
        if not paragraphs:
            paragraphs = response.css("div#main-detail-body p::text").getall()

        content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not content or len(content) < 100:
            logger.warning(f"Content too short ({len(content)} chars) from {response.url}")
            return

        # Stable ID Mapping (Canonical URL)
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
            source="tuoitre",
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
        logger.info(f"Tuoi Tre spider closed | reason={reason} | pages={self._page_count} | articles={self._article_count} | duration={elapsed}s")
