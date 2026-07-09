"""Higher-level RSS tools that compose the RSS/OPML parsers in ``rss.py`` (DRY).

- ``RSSFeedTool``: fetch recent news from a curated set of regional RSS feeds.
- ``UnifiedRssTool``: parse an OPML file, then fetch and aggregate every feed's entries.
"""

import json
import logging
import math
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, ClassVar

import feedparser
from crewai.tools import BaseTool
from dateutil import parser as date_parser
from pydantic import BaseModel, Field, PrivateAttr

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.web.rss import OpmlParserTool, RssFeedParserTool
from crewai_custom_tools.tools.web.rss_models import Article, FeedWithArticles, RssFeeds
from crewai_custom_tools.tools.web.scraper import UnifiedScraperTool

logger = logging.getLogger(__name__)

# Curated, working RSS feeds by region.
_RSS_SOURCES: dict[str, list[dict[str, str]]] = {
    "suisse_romande": [
        {
            "name": "Le Temps - Tous articles",
            "url": "https://www.letemps.ch/articles.rss",
            "language": "fr",
        },
        {
            "name": "Le Temps - Suisse",
            "url": "https://www.letemps.ch/suisse.rss",
            "language": "fr",
        },
        {
            "name": "Le Temps - Monde",
            "url": "https://www.letemps.ch/monde.rss",
            "language": "fr",
        },
        {
            "name": "Le Temps - Économie",
            "url": "https://www.letemps.ch/economie.rss",
            "language": "fr",
        },
    ],
    "france": [
        {
            "name": "Le Monde - À la Une",
            "url": "https://www.lemonde.fr/rss/une.xml",
            "language": "fr",
        },
        {
            "name": "Le Monde - International",
            "url": "https://www.lemonde.fr/international/rss_full.xml",
            "language": "fr",
        },
        {
            "name": "Le Figaro - À la Une",
            "url": "https://www.lefigaro.fr/rss/figaro_actualites.xml",
            "language": "fr",
        },
        {
            "name": "France 24",
            "url": "https://www.france24.com/fr/rss",
            "language": "fr",
        },
        {
            "name": "Les Échos",
            "url": "https://services.lesechos.fr/rss/les-echos-general.xml",
            "language": "fr",
        },
    ],
    "europe": [
        {
            "name": "BBC Europe",
            "url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
            "language": "en",
        },
        {"name": "Yahoo News", "url": "https://news.yahoo.com/rss/", "language": "en"},
    ],
    "world": [
        {
            "name": "BBC World News",
            "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "language": "en",
        },
        {
            "name": "Yahoo News International",
            "url": "https://news.yahoo.com/rss/",
            "language": "en",
        },
    ],
    "belgique": [
        {
            "name": "La Libre Belgique",
            "url": "https://www.lalibre.be/rss",
            "language": "fr",
        }
    ],
    "canada": [
        {
            "name": "Radio-Canada",
            "url": "https://ici.radio-canada.ca/rss",
            "language": "fr",
        }
    ],
}


class RSSFeedInput(BaseModel):
    """Input schema for RSSFeedTool."""

    region: str = Field(
        ...,
        description="Region key: suisse_romande, france, europe, world, belgique, canada.",
    )
    max_articles: int = Field(
        10, ge=1, le=100, description="Maximum number of articles to return."
    )
    hours_back: int = Field(
        24, ge=1, description="How far back to look (approximate; day-granular)."
    )


class RSSFeedTool(BaseTool):
    """Fetch recent news from a curated set of reliable regional RSS feeds."""

    name: str = "rss_feed_tool"
    description: str = (
        "Fetch recent news from curated, reliable regional RSS feeds (working links from "
        "established outlets). Supported regions: suisse_romande, france, europe, world, belgique, canada."
    )
    args_schema: type[BaseModel] = RSSFeedInput
    RSS_SOURCES: ClassVar[dict[str, list[dict[str, str]]]] = _RSS_SOURCES

    def _run(self, region: str, max_articles: int = 10, hours_back: int = 24) -> str:
        """Aggregate recent entries from every curated feed for the region."""
        sources = self.RSS_SOURCES.get(region)
        if not sources:
            return err(
                f"No RSS sources for region '{region}'. Options: {sorted(self.RSS_SOURCES)}"
            )

        days = max(1, math.ceil(hours_back / 24))
        parser = RssFeedParserTool()
        articles: list[dict] = []
        for source in sources:
            payload = json.loads(parser._run(feed_url=source["url"], days=days))
            if not payload["success"]:
                continue
            for entry in payload["data"]:
                articles.append(
                    {
                        **entry,
                        "source": source["name"],
                        "language": source.get("language"),
                    }
                )

        return ok(
            {
                "region": region,
                "count": min(len(articles), max_articles),
                "articles": articles[:max_articles],
            }
        )


class UnifiedRssToolInput(BaseModel):
    """Input schema for UnifiedRssTool."""

    opml_file_path: str = Field(
        ..., description="Path to an OPML file listing RSS feed sources."
    )
    days: int = Field(
        7, ge=1, description="Number of past days of entries to include per feed."
    )
    output_file_path: str | None = Field(
        None,
        description="Optional path to write the aggregated RssFeeds JSON. When set, the written file is the primary output.",
    )
    invalid_sources_file_path: str | None = Field(
        None,
        description="Optional path to write the list of feeds that errored or yielded no articles.",
    )


# Bound each feed fetch so a slow or hanging server can't stall the whole run
# (feedparser has no timeout arg; it honours the default socket timeout).
FEED_FETCH_TIMEOUT_S = 20.0


class UnifiedRssTool(BaseTool):
    """Parse an OPML file end to end: extract feeds, fetch and date-filter entries, scrape
    article content, and (optionally) persist the aggregated result as a RssFeeds JSON file."""

    name: str = "unified_rss_tool"
    description: str = (
        "Process an OPML subscription file end to end: extract every RSS feed URL, fetch each "
        "feed's recent entries, scrape article content, and aggregate them. When an output file "
        "path is provided the RssFeeds JSON is written to it (the file is the primary output)."
    )
    args_schema: type[BaseModel] = UnifiedRssToolInput
    _scraper: Any = PrivateAttr(default=None)

    def _get_scraper(self) -> Any:
        """Lazily build the resilient in-package scraper, reused across articles."""
        if self._scraper is None:
            self._scraper = UnifiedScraperTool()
        return self._scraper

    def _run(
        self,
        opml_file_path: str,
        days: int = 7,
        output_file_path: str | None = None,
        invalid_sources_file_path: str | None = None,
    ) -> str:
        """Parse the OPML, fetch/filter/scrape entries per feed, and aggregate or persist them."""
        opml_payload = json.loads(OpmlParserTool()._run(opml_file_path=opml_file_path))
        if not opml_payload["success"]:
            return err(opml_payload["error"])

        feed_urls = opml_payload["data"]
        invalid_sources: set[str] = set()
        # Inclusive, day-granular cutoff: normalise to 00:00 so any hour that day is kept.
        # Use naive-UTC to match entry dates: feedparser's *_parsed struct_times are UTC,
        # and _entry_pub_date normalises string dates to UTC too. datetime.now() (naive
        # local) would skew the boundary by the server's UTC offset on non-UTC hosts.
        cutoff_date = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        ).replace(hour=0, minute=0, second=0, microsecond=0)

        all_feeds: list[FeedWithArticles] = []
        for feed_url in feed_urls:
            articles = self._fetch_and_filter_articles(
                feed_url, cutoff_date, invalid_sources
            )
            if articles:
                all_feeds.append(FeedWithArticles(feed_url=feed_url, articles=articles))
            else:
                invalid_sources.add(feed_url)

        # Scrape content for each article, falling back to the RSS summary on failure.
        for feed in all_feeds:
            for article in feed.articles:
                scraped = self._scrape_article_content(article.link)
                if scraped:
                    article.content = scraped
                elif article.summary:
                    article.content = article.summary

        rss_feeds = RssFeeds(rss_feeds=all_feeds)

        if output_file_path:
            output_dir = os.path.dirname(output_file_path)
            if output_dir:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
            with open(output_file_path, "w", encoding="utf-8") as fh:
                json.dump(rss_feeds.model_dump(), fh, ensure_ascii=False, indent=2)
            logger.info(
                f"UnifiedRssTool wrote {len(all_feeds)} feeds to {output_file_path}"
            )

        if invalid_sources and invalid_sources_file_path:
            inv_dir = os.path.dirname(invalid_sources_file_path)
            if inv_dir:
                Path(inv_dir).mkdir(parents=True, exist_ok=True)
            with open(invalid_sources_file_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "invalid_sources": sorted(invalid_sources),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "total_invalid": len(invalid_sources),
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(
                f"UnifiedRssTool recorded {len(invalid_sources)} invalid sources to {invalid_sources_file_path}"
            )

        total_articles = sum(len(f.articles) for f in all_feeds)
        return ok(
            {
                "feeds": len(all_feeds),
                "articles": total_articles,
                "invalid_sources": sorted(invalid_sources),
                "output_file_path": output_file_path,
            }
        )

    def _fetch_and_filter_articles(
        self, feed_url: str, cutoff_date: datetime, invalid_sources: set[str]
    ) -> list[Article]:
        """Fetch a feed and return Articles newer than ``cutoff_date``; track invalid feeds."""
        try:
            # Bound the network fetch: feedparser has no timeout arg but honours the
            # default socket timeout. A slow/hanging feed then raises (caught below and
            # marked invalid) instead of stalling the whole aggregation run.
            previous_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(FEED_FETCH_TIMEOUT_S)
            try:
                feed = feedparser.parse(feed_url)
            finally:
                socket.setdefaulttimeout(previous_timeout)

            status = getattr(feed, "status", None)
            if status is not None:
                try:
                    if int(status) >= 400:
                        invalid_sources.add(feed_url)
                        return []
                except (TypeError, ValueError):
                    pass  # non-integer status: treat as unknown, keep going

            if getattr(feed, "bozo", False):
                invalid_sources.add(feed_url)
                return []

            articles: list[Article] = []
            for entry in feed.entries:
                pub_date = self._entry_pub_date(entry)
                if not pub_date or pub_date < cutoff_date:
                    continue
                articles.append(
                    Article(
                        title=entry.get("title", "No Title"),
                        link=entry.get("link", ""),
                        published=pub_date.isoformat(),
                        summary=entry.get("summary"),
                        content=None,  # populated by the scraping pass
                    )
                )
            return articles
        except Exception as exc:  # noqa: BLE001 — any feed error marks the source invalid
            logger.warning(f"Error fetching feed {feed_url}: {exc}")
            invalid_sources.add(feed_url)
            return []

    @staticmethod
    def _entry_pub_date(entry: Any) -> datetime | None:
        """Best-effort naive-UTC publication date: struct_time fields first, then strings.

        feedparser normalises ``*_parsed`` struct_times to UTC, so ``datetime(*parsed[:6])``
        is already naive-UTC. String dates may carry any offset, so convert tz-aware values
        to UTC before dropping tzinfo; naive strings are assumed UTC. This keeps every
        returned datetime comparable to the naive-UTC cutoff.
        """
        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    return datetime(*parsed[:6])  # struct_time is UTC -> naive-UTC
                except (TypeError, ValueError):
                    pass
        for attr in ("published", "updated"):
            value = getattr(entry, attr, None)
            if value:
                try:
                    dt = date_parser.parse(value)
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc)
                    return dt.replace(tzinfo=None)
                except (TypeError, ValueError):
                    pass
        return None

    def _scrape_article_content(self, url: str) -> str | None:
        """Scrape readable article text, staying pure-Python-friendly (ADR-0002).

        Order: optional Newspaper3k (only if the caller installed it) -> the in-package
        resilient UnifiedScraperTool (requests + BeautifulSoup, auto-escalating to
        ScrapeNinja/Firecrawl when their keys are set) -> None (caller uses the RSS summary).
        """
        if not url:
            return None

        # 1. Best-effort Newspaper3k — never a hard dependency of this package.
        try:
            from newspaper import Article as NewspaperArticle

            article = NewspaperArticle(url)
            article.download()
            article.parse()
            if article.text and len(article.text.strip()) > 100:
                return str(article.text)
        except Exception as exc:  # noqa: BLE001 — ImportError or any scrape error
            logger.debug(f"Newspaper3k unavailable/failed for {url}: {exc}")

        # 2. Fall back to the package's own resilient scraper.
        try:
            payload = json.loads(self._get_scraper()._run(url=url))
            if payload.get("success"):
                content = (payload.get("data") or {}).get("content")
                if content:
                    return str(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"UnifiedScraperTool failed for {url}: {exc}")

        return None
