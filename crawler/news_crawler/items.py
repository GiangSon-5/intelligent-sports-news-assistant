"""
Crawler Module — items.py
Scrapy Item definitions according to SPEC §2.1.
Global Data Contract: Article Schema (7 fields).
"""

import scrapy


class NewsArticleItem(scrapy.Item):
    """
    Schema for an article collected from the source.
    Matches 100% with Global Data Contract in README_MASTER.md §5.1.
    """

    title = scrapy.Field()           # str: Article title
    content = scrapy.Field()         # str: Full content
    publish_date = scrapy.Field()    # str: Publication date (ISO 8601 after normalization)
    source = scrapy.Field()          # str: Enum ['vnexpress', 'thanhnien', 'tuoitre']
    url = scrapy.Field()             # str: Original article URL
    crawled_at = scrapy.Field()      # str: ISO 8601 timestamp when crawled
    article_id = scrapy.Field()      # str: SHA256(canonical_url) — unique identifier
    
    # --- New Fields for Change Tracking ---
    title_hash = scrapy.Field()      # str: Hash of the title
    content_hash = scrapy.Field()    # str: Hash of the content
    version = scrapy.Field()         # int: Version number (1, 2, ...)
    update_type = scrapy.Field()     # str: Enum ['new', 'title', 'content', 'both']
    last_updated_at = scrapy.Field() # str: ISO 8601 timestamp of last detected change
