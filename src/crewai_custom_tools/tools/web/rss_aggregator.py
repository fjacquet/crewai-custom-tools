"""Higher-level RSS tools that compose the RSS/OPML parsers in ``rss.py`` (DRY).

- ``RSSFeedTool``: fetch recent news from a curated set of regional RSS feeds.
- ``UnifiedRssTool``: parse an OPML file, then fetch and aggregate every feed's entries.
"""

import json
import math
from typing import ClassVar

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.web.rss import OpmlParserTool, RssFeedParserTool

# Curated, working RSS feeds by region.
_RSS_SOURCES: dict[str, list[dict[str, str]]] = {
    "suisse_romande": [
        {"name": "Le Temps - Tous articles", "url": "https://www.letemps.ch/articles.rss", "language": "fr"},
        {"name": "Le Temps - Suisse", "url": "https://www.letemps.ch/suisse.rss", "language": "fr"},
        {"name": "Le Temps - Monde", "url": "https://www.letemps.ch/monde.rss", "language": "fr"},
        {"name": "Le Temps - Économie", "url": "https://www.letemps.ch/economie.rss", "language": "fr"},
    ],
    "france": [
        {"name": "Le Monde - À la Une", "url": "https://www.lemonde.fr/rss/une.xml", "language": "fr"},
        {"name": "Le Monde - International", "url": "https://www.lemonde.fr/international/rss_full.xml", "language": "fr"},
        {"name": "Le Figaro - À la Une", "url": "https://www.lefigaro.fr/rss/figaro_actualites.xml", "language": "fr"},
        {"name": "France 24", "url": "https://www.france24.com/fr/rss", "language": "fr"},
        {"name": "Les Échos", "url": "https://services.lesechos.fr/rss/les-echos-general.xml", "language": "fr"},
    ],
    "europe": [
        {"name": "BBC Europe", "url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "language": "en"},
        {"name": "Yahoo News", "url": "https://news.yahoo.com/rss/", "language": "en"},
    ],
    "world": [
        {"name": "BBC World News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "language": "en"},
        {"name": "Yahoo News International", "url": "https://news.yahoo.com/rss/", "language": "en"},
    ],
    "belgique": [{"name": "La Libre Belgique", "url": "https://www.lalibre.be/rss", "language": "fr"}],
    "canada": [{"name": "Radio-Canada", "url": "https://ici.radio-canada.ca/rss", "language": "fr"}],
}


class RSSFeedInput(BaseModel):
    """Input schema for RSSFeedTool."""

    region: str = Field(..., description="Region key: suisse_romande, france, europe, world, belgique, canada.")
    max_articles: int = Field(10, ge=1, le=100, description="Maximum number of articles to return.")
    hours_back: int = Field(24, ge=1, description="How far back to look (approximate; day-granular).")


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
            return err(f"No RSS sources for region '{region}'. Options: {sorted(self.RSS_SOURCES)}")

        days = max(1, math.ceil(hours_back / 24))
        parser = RssFeedParserTool()
        articles: list[dict] = []
        for source in sources:
            payload = json.loads(parser._run(feed_url=source["url"], days=days))
            if not payload["success"]:
                continue
            for entry in payload["data"]:
                articles.append({**entry, "source": source["name"], "language": source.get("language")})

        return ok({"region": region, "count": min(len(articles), max_articles), "articles": articles[:max_articles]})


class UnifiedRssToolInput(BaseModel):
    """Input schema for UnifiedRssTool."""

    opml_file_path: str = Field(..., description="Path to an OPML file listing RSS feed sources.")
    days: int = Field(7, ge=1, description="Number of past days of entries to include per feed.")
    max_articles: int = Field(50, ge=1, le=500, description="Maximum number of aggregated articles.")


class UnifiedRssTool(BaseTool):
    """Parse an OPML file, fetch recent entries from every feed, and aggregate them."""

    name: str = "unified_rss_tool"
    description: str = (
        "Process an OPML subscription file end to end: extract every RSS feed URL, fetch each "
        "feed's recent entries, and return them aggregated."
    )
    args_schema: type[BaseModel] = UnifiedRssToolInput

    def _run(self, opml_file_path: str, days: int = 7, max_articles: int = 50) -> str:
        """Parse the OPML, then fetch and merge entries from each feed."""
        opml_payload = json.loads(OpmlParserTool()._run(opml_file_path=opml_file_path))
        if not opml_payload["success"]:
            return err(opml_payload["error"])

        feed_urls = opml_payload["data"]
        parser = RssFeedParserTool()
        articles: list[dict] = []
        for url in feed_urls:
            payload = json.loads(parser._run(feed_url=url, days=days))
            if payload["success"]:
                for entry in payload["data"]:
                    articles.append({**entry, "feed_url": url})

        return ok({"feeds": len(feed_urls), "count": min(len(articles), max_articles), "articles": articles[:max_articles]})
