"""
Spider: VnExpress — https://vnexpress.net/the-thao
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

logger = logging.getLogger("sports_assistant.crawler.vnexpress")
_VN_TZ = timezone(timedelta(hours=7))
_MAX_PAGES = 50


class VnexpressSpider(scrapy.Spider):
    name = "vnexpress"
    allowed_domains = ["vnexpress.net"]
    start_urls = ["https://vnexpress.net/the-thao"]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_count = 0
        self._article_count = 0
        self._start_time = time.perf_counter()
        self.stop_date = None # Will be set in start_requests

    def start_requests(self):
        # Dynamic crawl range from settings (defaults to 7 if not set)
        days_to_crawl = self.settings.getint("CRAWL_DAYS_BACK", 7)
        self.stop_date = datetime.now(_VN_TZ) - timedelta(days=days_to_crawl)
        logger.info(f"Spider started | stop_date={self.stop_date.strftime('%Y-%m-%d')} ({days_to_crawl} days)")

        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    # ------------------------------------------------------------------
    #  Phase 1: LIST PAGE
    # ------------------------------------------------------------------

    def parse(self, response):
        """Parse listing page — extract article URLs."""
        start = time.perf_counter()
        self._page_count += 1

        # Selector: article links (SPEC §3.2)
        article_links = response.css("h2.title-news a::attr(href), h3.title-news a::attr(href)").getall()
        
        # Fallback selectors if primary doesn't match
        if not article_links:
            article_links = response.css("article.item-news a::attr(href)").getall()
            article_links = [l for l in article_links if l.endswith(".html")]

        if not article_links:
            logger.warning(f"No articles found on {response.url} (Edge Case #8)")
        else:
            logger.info(f"Found {len(article_links)} articles on page {self._page_count}")

        # Yield requests for detail pages
        for link in article_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_article,
                errback=self.handle_error,
                meta={"listing_url": response.url},
            )

        # Pagination (maximum _MAX_PAGES)
        if self._page_count < _MAX_PAGES:
            next_page = response.css("a.btn-page.next-page::attr(href)").get()
            if not next_page:
                next_page = response.css("a.next-page::attr(href)").get()
            if not next_page:
                next_page = response.css("a[rel='next']::attr(href)").get()

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
        """Parse detail page — extract article content."""
        start = time.perf_counter()

        # Title (SPEC §3.2)
        title = response.css("h1.title-detail::text").get()
        if not title:
            title = response.css("h1::text").get()
        if not title:
            logger.warning(f"Failed to extract title from {response.url} (Edge Case #1)")
            return

        title = title.strip()

        # Content
        paragraphs = response.css("article.fck_detail p::text").getall()
        if not paragraphs:
            paragraphs = response.css("article.fck_detail p *::text").getall()
        if not paragraphs:
            paragraphs = response.css("div.fck_detail p::text").getall()

        content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not content or len(content) < 100:
            logger.warning(f"Content too short ({len(content)} chars) from {response.url}")
            return

        # Date
        raw_date = response.css("span.date::text").get()
        if not raw_date:
            raw_date = response.css("span.time::text").get()
        if not raw_date:
            raw_date = response.css("div.header-content span::text").get()
        raw_date = (raw_date or "").strip()
        
        # --- NEW: Early Stopping Logic ---
        try:
            # Clean: "Thứ hai, 6/5/2026, 12:30 (GMT+7)"
            clean_date = re.sub(r"(Thứ\s+[a-z0-9]+|Chủ\s+nhật|T[2-7]|CN)[\s,]*", "", raw_date, flags=re.IGNORECASE)
            clean_date = re.sub(r"\(?GMT[+-]\d+\)?", "", clean_date).strip()
            
            match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})[\s,]*(\d{1,2}):(\d{2})", clean_date)
            if match:
                d, mo, y, h, m = [int(x) for x in match.groups()]
                dt = datetime(y, mo, d, h, m, tzinfo=_VN_TZ)
                if dt < self.stop_date:
                    logger.info(f"Article is older than stop_date ({dt} < {self.stop_date}). Skipping.")
                    return # Skip this item
        except Exception as e:
            logger.debug(f"Date check failed on detail page: {e}")

        # Stable ID Mapping & Content Fingerprinting
        canonical_url = response.css("link[rel='canonical']::attr(href)").get() or response.url
        article_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        
        # Calculate Hashes for Change Detection
        title_hash = hashlib.sha256(title.encode("utf-8")).hexdigest()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        now = datetime.now(_VN_TZ).isoformat()

        self._article_count += 1

        item = NewsArticleItem(
            title=title,
            content=content,
            publish_date=raw_date,
            source="vnexpress",
            url=response.url,
            crawled_at=now,
            article_id=article_id,
            # --- New Fields ---
            title_hash=title_hash,
            content_hash=content_hash,
            version=1,
            update_type="new",
            last_updated_at=now,
        )

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.debug(
            f"Article #{self._article_count} parsed | title='{title[:40]}...' | "
            f"chars={len(content)} | latency={elapsed}ms"
        )

        yield item

    # ------------------------------------------------------------------
    #  Error Handler
    # ------------------------------------------------------------------

    def handle_error(self, failure):
        """Handle request failures gracefully (Edge Case #2, #7)."""
        logger.error(
            f"Request failed | url={failure.request.url} | "
            f"error={failure.type.__name__}: {failure.value}"
        )

    def closed(self, reason):
        """Spider closed callback — log final stats."""
        elapsed = round(time.perf_counter() - self._start_time, 1)
        logger.info(
            f"VnExpress spider closed | reason={reason} | "
            f"pages={self._page_count} | articles={self._article_count} | "
            f"duration={elapsed}s"
        )
