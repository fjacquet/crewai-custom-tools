"""Wikipedia search and article extraction tools."""

import logging
import urllib.parse
from enum import StrEnum

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


class ArticleAction(StrEnum):
    """Actions that can be performed on a Wikipedia article."""

    GET_SUMMARY = "get_summary"
    GET_ARTICLE = "get_article"
    GET_SECTIONS = "get_sections"


class WikipediaSearchToolInput(BaseModel):
    """Input model for the WikipediaSearchTool."""

    query: str = Field(..., description="The search query for Wikipedia.")
    limit: int = Field(
        default=5, description="The maximum number of results to return."
    )


class WikipediaSearchTool(BaseTool):
    """A tool to search for articles on Wikipedia."""

    name: str = "Wikipedia Search"
    description: str = "Searches Wikipedia for articles matching a query and returns a list of matching titles."
    args_schema: type[BaseModel] = WikipediaSearchToolInput

    @api_tool(provider="Wikipedia", endpoint="Search")
    def _run(self, query: str, limit: int = 5) -> str:
        """Run the Wikipedia search tool using the MediaWiki API."""
        encoded_query = urllib.parse.quote(query)
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={encoded_query}&utf8=&format=json&srlimit={limit}"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        search_results = response.json().get("query", {}).get("search", [])
        return ok([item.get("title") for item in search_results])


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
    description: str = "Fetches content (summary, full article, or section titles) from a specified Wikipedia article."
    args_schema: type[BaseModel] = WikipediaArticleToolInput

    @api_tool(provider="Wikipedia", endpoint="ArticleFetcher")
    def _run(
        self, title: str, action: ArticleAction = ArticleAction.GET_SUMMARY
    ) -> str:
        """Fetch article content via the English Wikipedia REST/MediaWiki API."""
        encoded_title = urllib.parse.quote(title)

        if action == ArticleAction.GET_SUMMARY:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                return err(f"No Wikipedia page found for '{title}'")
            response.raise_for_status()
            return ok({"title": title, "summary": response.json().get("extract", "")})

        if action == ArticleAction.GET_SECTIONS:
            # Use the parse API's structured section list rather than parsing the
            # plaintext extract (whose '==' header markers are stripped away).
            url = (
                "https://en.wikipedia.org/w/api.php?action=parse&prop=sections"
                f"&page={encoded_title}&format=json"
            )
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return err(f"No Wikipedia page found for '{title}'")
            sections = [s.get("line") for s in data.get("parse", {}).get("sections", [])]
            return ok({"title": title, "sections": sections})

        # GET_ARTICLE — full plaintext extract.
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
            f"&explaintext=1&titles={encoded_title}&format=json"
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        if not pages or "-1" in pages:
            return err(f"No Wikipedia page found for '{title}'")
        page_data = next(iter(pages.values()))
        return ok({"title": title, "content": page_data.get("extract", "")})
