"""Wikipedia search and article extraction tools."""

import json
import logging
import urllib.parse
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Optional
from enum import StrEnum
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


class ArticleAction(StrEnum):
    """Actions that can be performed on a Wikipedia article."""

    GET_SUMMARY = "get_summary"
    GET_ARTICLE = "get_article"
    GET_SECTIONS = "get_sections"


class WikipediaSearchToolInput(BaseModel):
    """Input model for the WikipediaSearchTool."""

    query: str = Field(..., description="The search query for Wikipedia.")
    limit: Optional[int] = Field(
        default=5, description="The maximum number of results to return."
    )


class WikipediaSearchTool(BaseTool):
    """A tool to search for articles on Wikipedia."""

    name: str = "Wikipedia Search"
    description: str = "Searches Wikipedia for articles matching a query and returns a list of matching titles."
    args_schema: type[BaseModel] = WikipediaSearchToolInput

    @api_tool(provider="Wikipedia", endpoint="Search", default_return="[]")
    def _run(self, query: str, limit: int = 5) -> str:
        """Run the Wikipedia search tool using MediaWiki REST API."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&utf8=&format=json&srlimit={limit}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        search_results = data.get("query", {}).get("search", [])
        results = [item.get("title") for item in search_results]
        return json.dumps(results)


class WikipediaArticleToolInput(BaseModel):
    """Input model for the WikipediaArticleTool."""

    title: str = Field(..., description="The title of the Wikipedia article.")
    action: ArticleAction = Field(
        default=ArticleAction.GET_SUMMARY,
        description="The action to perform on the article.",
    )


class WikipediaArticleTool(BaseTool):
    """A tool to fetch various types of content from a Wikipedia article."""

    name: str = "Wikipedia Article Fetcher"
    description: str = "Fetches content (summary, full article sections, etc.) from a specified Wikipedia article."
    args_schema: type[BaseModel] = WikipediaArticleToolInput

    @api_tool(
        provider="Wikipedia",
        endpoint="ArticleFetcher",
        default_return="Error: Failed to fetch Wikipedia content.",
    )
    def _run(
        self, title: str, action: ArticleAction = ArticleAction.GET_SUMMARY
    ) -> str:
        """Fetch article content via English Wikipedia REST/MediaWiki API."""
        encoded_title = urllib.parse.quote(title)

        # 1. Action: Summary
        if action == ArticleAction.GET_SUMMARY:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                return f"Could not find a Wikipedia page for '{title}'. Please check the spelling."
            response.raise_for_status()
            data = response.json()
            return data.get("extract", "No extract found.")

        # 2. Action: Full text or sections
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={encoded_title}&format=json"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages or "-1" in pages:
            return f"Could not find a Wikipedia page for '{title}'."

        page_id = list(pages.keys())[0]
        page_data = pages[page_id]
        extract = page_data.get("extract", "")

        if action == ArticleAction.GET_ARTICLE:
            return extract

        if action == ArticleAction.GET_SECTIONS:
            # Parse sections simply based on header lines (e.g. == Section Title ==)
            sections = []
            current_section = "Intro"
            current_content = []

            for line in extract.splitlines():
                if line.startswith("==") and line.endswith("=="):
                    if current_content:
                        sections.append(
                            {
                                "title": current_section,
                                "content": "\n".join(current_content).strip(),
                            }
                        )
                    current_section = line.strip("=").strip()
                    current_content = []
                else:
                    current_content.append(line)
            if current_content:
                sections.append(
                    {
                        "title": current_section,
                        "content": "\n".join(current_content).strip(),
                    }
                )

            return json.dumps(sections)

        return f"Error: Unknown action '{action}'."
