"""RSS feed parsing and OPML subscription utilities."""

import logging
from datetime import datetime, timedelta, timezone

# defusedxml guards against XXE / billion-laughs attacks in untrusted OPML files.
from defusedxml.ElementTree import ParseError, parse as parse_xml

import feedparser
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


def _entry_dict(entry, published: str) -> dict:
    """Build a normalized entry record from a feedparser entry."""
    return {
        "title": entry.get("title", "No Title"),
        "link": entry.get("link", ""),
        "published": published,
        "summary": entry.get("summary", "")[:300] if hasattr(entry, "summary") else "",
    }


class RssFeedParserInput(BaseModel):
    """Input model for the RssFeedParserTool."""

    feed_url: str = Field(..., description="The RSS feed URL to parse.")
    days: int = Field(
        default=7, description="Number of past days of entries to return (default: 7)."
    )


class RssFeedParserTool(BaseTool):
    """A tool for parsing RSS feeds to fetch recent posts and news."""

    name: str = "rss_feed_parser"
    description: str = "A tool for parsing an RSS feed and returning recent entries. It requires the RSS feed URL."
    args_schema: type[BaseModel] = RssFeedParserInput

    @api_tool(provider="RSS", endpoint="ParseFeed")
    def _run(self, feed_url: str, days: int = 7) -> str:
        """Parse an RSS feed and return entries newer than the cutoff."""
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            logger.warning(
                f"Feed at {feed_url} is not well-formed: {feed.get('bozo_exception', 'Unknown')}"
            )
        if getattr(feed, "status", 0) and feed.status >= 400:
            return err(f"Failed to fetch RSS feed, status code {feed.status}")

        # feedparser normalizes published_parsed to UTC — compare in UTC too.
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent_entries = []
        for entry in feed.entries:
            parsed = getattr(entry, "published_parsed", None)
            if not parsed:
                recent_entries.append(_entry_dict(entry, "Unknown"))
                continue
            try:
                published_time = datetime(*parsed[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse date for an entry in {feed_url}.")
                continue
            if published_time >= cutoff:
                recent_entries.append(_entry_dict(entry, entry.get("published", "")))

        return ok(recent_entries)


class OpmlParserInput(BaseModel):
    """Input schema for OpmlParserTool."""

    opml_file_path: str = Field(
        ..., description="The absolute or relative path to the OPML file to be parsed."
    )


class OpmlParserTool(BaseTool):
    """A tool to parse OPML files to discover feed URLs."""

    name: str = "opml_parser"
    description: str = (
        "Parses an OPML subscription file to extract standard RSS feed URLs."
    )
    args_schema: type[BaseModel] = OpmlParserInput

    @api_tool(provider="OPML", endpoint="ParseFile")
    def _run(self, opml_file_path: str) -> str:
        """Parse the OPML file and extract all xmlUrl attributes."""
        try:
            root = parse_xml(opml_file_path).getroot()
        except ParseError as e:
            return err(f"Error parsing OPML file: {e}")
        except FileNotFoundError:
            return err(f"OPML file not found at {opml_file_path}")

        urls = [
            url
            for outline in root.findall(".//outline[@xmlUrl]")
            if (url := outline.get("xmlUrl"))
        ]
        return ok(urls)
