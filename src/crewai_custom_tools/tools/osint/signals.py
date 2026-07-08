"""News-signal OSINT tools: GDELT DOC 2.0 and Google News RSS (both keyless).

Sync `requests`/`feedparser` rewrites of the osint_tools signal providers — the
GDELT `gdeltdoc` client is replaced by a direct call to GDELT's public HTTP
endpoint so no extra dependency is needed.
"""

from urllib.parse import quote, urlparse

import feedparser
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok

_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)


class NewsQueryInput(BaseModel):
    """Input schema for a news-mention search."""

    name: str = Field(
        ..., description="Company, person, or topic name to find news mentions for."
    )


class GdeltTool(BaseTool):
    """Recent worldwide news mentions for a name via GDELT DOC 2.0 (keyless)."""

    name: str = "gdelt_news_mentions"
    description: str = (
        "Find recent worldwide news mentions of a company/person/topic via GDELT's "
        "public DOC 2.0 API. Returns article titles, URLs, domains and dates. Keyless."
    )
    args_schema: type[BaseModel] = NewsQueryInput

    @api_tool(provider="GDELT", endpoint="ArtList")
    def _run(self, name: str) -> str:
        """Query GDELT DOC 2.0 ArtList for recent articles mentioning ``name``."""
        params = {
            "query": name,
            "mode": "ArtList",
            "format": "json",
            "timespan": "1months",
            "maxrecords": 50,
        }
        response = requests.get(_GDELT_URL, params=params, timeout=15)
        response.raise_for_status()
        # GDELT returns JSON with an `articles` list; an empty result can be a
        # non-JSON/empty body, so parse defensively.
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        items = [
            {
                "title": a.get("title"),
                "url": a.get("url"),
                "domain": a.get("domain"),
                "seendate": a.get("seendate"),
            }
            for a in articles
            if a.get("title") and a.get("url")
        ]
        return ok({"name": name, "articles": items})


class GoogleNewsRssTool(BaseTool):
    """Recent news mentions for a name via Google News RSS (keyless)."""

    name: str = "google_news_rss"
    description: str = (
        "Find recent news mentions of a company/person/topic via Google News' public "
        "RSS search. Returns headlines, links, sources and dates. Keyless."
    )
    args_schema: type[BaseModel] = NewsQueryInput

    @api_tool(provider="GoogleNews", endpoint="RSS")
    def _run(self, name: str) -> str:
        """Parse Google News RSS search results for ``name``."""
        url = _GOOGLE_NEWS_URL.format(query=quote(name))
        feed = feedparser.parse(url)

        items = []
        for entry in feed.get("entries", []):
            title = entry.get("title")
            link = entry.get("link")
            if not title or not link:
                continue
            source = entry.get("source") or {}
            href = source.get("href") if isinstance(source, dict) else None
            domain = urlparse(href).netloc or None if href else None
            items.append(
                {
                    "title": title,
                    "url": link,
                    "domain": domain,
                    "published": entry.get("published"),
                }
            )
        return ok({"name": name, "articles": items})
