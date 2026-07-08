"""Google Serper search tool implementation."""

import logging
import os

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


class SerperSearchInput(BaseModel):
    """Input schema for Serper Search Tool."""

    query: str = Field(..., description="The query to search Google for.")


class SerperSearchTool(BaseTool):
    """A robust web search tool using the Serper.dev API."""

    name: str = "search_internet"
    description: str = (
        "A tool to search the internet for up-to-date information on any topic. "
        "Use this tool when you need current data or facts about events, people, or concepts."
    )
    args_schema: type[BaseModel] = SerperSearchInput

    @api_tool(provider="Serper", endpoint="Search")
    def _run(self, query: str) -> str:
        """Execute the search query against Serper.dev."""
        # Agents sometimes pass a dict instead of a bare string.
        if not isinstance(query, str):
            d = query if isinstance(query, dict) else {}
            query = str(
                d.get("query") or d.get("search_query") or d.get("description") or query
            )

        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return err("SERPER_API_KEY not configured")

        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        results = [
            {
                "title": item.get("title", "No title"),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
            }
            for item in data.get("organic", [])[:5]
        ]
        return ok({"query": query, "results": results})
