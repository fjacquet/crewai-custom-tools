"""RSS feed parsing and OPML subscription utilities."""

import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import feedparser
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, List, Union
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


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

    @api_tool(provider="RSS", endpoint="ParseFeed", default_return="[]")
    def _run(self, feed_url: str, days: int = 7) -> str:
        """Run the RSS feed parser tool with robust error handling."""
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            logger.warning(
                f"Feed at {feed_url} is not well-formed. Reason: {feed.get('bozo_exception', 'Unknown')}"
            )

        if hasattr(feed, "status") and feed.status >= 400:
            logger.error(f"Feed at {feed_url} returned HTTP status {feed.status}")
            return f"Error: Failed to fetch RSS feed, status code {feed.status}"

        cutoff_date = datetime.now() - timedelta(days=days)

        recent_entries = []
        for entry in feed.entries:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_time = datetime(*entry.published_parsed[:6])
                    if published_time >= cutoff_date:
                        recent_entries.append(
                            {
                                "title": entry.get("title", "No Title"),
                                "link": entry.get("link", ""),
                                "published": entry.get("published", ""),
                                "summary": entry.get("summary", "")[:300]
                                if hasattr(entry, "summary")
                                else "",
                            }
                        )
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not parse date for an entry in {feed_url}. Title: {entry.get('title', 'N/A')}"
                    )
                    continue
            else:
                # Fallback if no publication date is present
                recent_entries.append(
                    {
                        "title": entry.get("title", "No Title"),
                        "link": entry.get("link", ""),
                        "published": "Unknown",
                        "summary": entry.get("summary", "")[:300]
                        if hasattr(entry, "summary")
                        else "",
                    }
                )

        return json.dumps(recent_entries, default=str)


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

    @api_tool(provider="OPML", endpoint="ParseFile", default_return="[]")
    def _run(self, opml_file_path: str) -> Union[List[str], str]:
        """Parses the OPML file and extracts all xmlUrl attributes."""
        try:
            tree = ET.parse(opml_file_path)
            root = tree.getroot()
            urls = []
            for outline in root.findall(".//outline[@xmlUrl]"):
                url = outline.get("xmlUrl")
                if url:
                    urls.append(url)
            return urls
        except ET.ParseError as e:
            return f"Error parsing XML file: {e}"
        except FileNotFoundError:
            return f"Error: The file was not found at {opml_file_path}"
