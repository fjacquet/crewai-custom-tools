"""Pydantic models describing the aggregated RSS output written by ``UnifiedRssTool``.

The JSON shape here is the cross-repo contract consumed by epic_news's RSS weekly
pipeline (``utils/rss_utils.py`` writes the file, ``RssWeeklyCrew`` reads it), so the
field names must stay in lockstep with epic_news's ``models/rss_models.py``.
"""

from __future__ import annotations

from pydantic import BaseModel


class Article(BaseModel):
    """A single article extracted from an RSS feed."""

    title: str
    link: str
    published: str
    summary: str | None = None
    content: str | None = None


class FeedWithArticles(BaseModel):
    """A single RSS feed and its list of recent articles."""

    feed_url: str
    articles: list[Article]


class RssFeeds(BaseModel):
    """A collection of RSS feeds, each with its recent articles."""

    rss_feeds: list[FeedWithArticles]
