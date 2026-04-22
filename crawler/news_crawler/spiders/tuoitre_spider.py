"""
Spider: Tuổi Trẻ — https://tuoitre.vn/the-thao.htm
2-phase crawling: listing page → detail page.
Selectors according to SPEC §3.2.
"""

import hashlib
import logging
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
    start_urls = ["https://tuoitre.vn/the-thao.htm"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_count = 0
        self._article_count = 0
        self._start_time = time.perf_counter()

    # ------------------------------------------------------------------
    #  Phase 1: LIST PAGE
    # ------------------------------------------------------------------

    def parse(self, response):
        start = time.perf_counter()
        self._page_count += 1

        # Selector: Tuổi Trẻ article links (SPEC §3.2)
        article_links = response.css("h3.box-title-text a::attr(href)").getall()

        # Fallback selectors
        if not article_links:
            article_links = response.css("h2.box-title-text a::attr(href)").getall()
        if not article_links:
            article_links = response.css("a.box-category-link-title::attr(href)").getall()
        if not article_links:
            article_links = response.css("li.news-item a::attr(href)").getall()
            article_links = [l for l in article_links if l.endswith(".htm")]

        if not article_links:
            logger.warning(f"No articles found on {response.url}")
        else:
            logger.info(f"Found {len(article_links)} articles on page {self._page_count}")

        for link in article_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_article,
                errback=self.handle_error,
            )

        # Pagination
        if self._page_count < _MAX_PAGES:
            next_page = response.css("a.page-next::attr(href)").get()
            if not next_page:
                next_page = response.css("a[rel='next']::attr(href)").get()
            if not next_page:
                next_page = response.css("ul.pager a.active + a::attr(href)").get()

            if next_page:
                yield scrapy.Request(
                    url=response.urljoin(next_page),
                    callback=self.parse,
                    errback=self.handle_error,
                )

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(f"Listing parse done | url={response.url} | latency={elapsed}ms")

    # ------------------------------------------------------------------
    #  Phase 2: DETAIL PAGE
    # ------------------------------------------------------------------

    def parse_article(self, response):
        start = time.perf_counter()

        # Title (SPEC §3.2)
        title = response.css("h1.detail-title::text").get()
        if not title:
            title = response.css("h1.article-title::text").get()
        if not title:
            title = response.css("h1::text").get()
        if not title:
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

        # Date (Exhaustive & Accurate)
        raw_date = response.css("div.detail-time [data-role='publishdate']::text").get()
        if not raw_date:
            raw_date = response.css("meta[property='article:published_time']::attr(content)").get()
        if not raw_date:
            raw_date = response.css("span.detail-time::text").get()
        if not raw_date:
            raw_date = response.css("div.detail-time span::text").get()
        if not raw_date:
            raw_date = response.css("time::attr(datetime)").get()
        
        raw_date = (raw_date or "").strip()

        # Stable ID Mapping (Canonical URL)
        canonical_url = response.css("link[rel='canonical']::attr(href)").get() or response.url
        article_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        
        # Fingerprinting (Change Detection)
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
            # --- Versioning ---
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
