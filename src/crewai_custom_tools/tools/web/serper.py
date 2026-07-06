"""Google Serper search tool implementation."""

import logging
import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


class SerperSearchInput(BaseModel):
    """Input schema for Serper Search Tool."""

    query: str = Field(..., description="The query to search Google for.")


class SerperSearchTool(BaseTool):
    """A robust web search tool using Serper API with improved error handling."""

    name: str = "search_internet"
    description: str = (
        "A tool to search the internet for up-to-date information on any topic. "
        "Use this tool when you need current data or facts about events, people, or concepts."
    )
    args_schema: type[BaseModel] = SerperSearchInput

    @api_tool(
        provider="Serper",
        endpoint="Search",
        default_return="Error performing search: API call failed.",
    )
    def _run(self, query: str) -> str:
        """Execute the search query with error handling."""
        # Validation and normalization (agents sometimes pass dicts)
        if not isinstance(query, str):
            d = query if isinstance(query, dict) else {}
            query = str(
                d.get("query") or d.get("search_query") or d.get("description") or query
            )

        api_key = os.getenv("SERPLY_API_KEY") or os.getenv("SERPER_API_KEY")
        if not api_key:
            return "Error: SERPER_API_KEY environment variable not set"

        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        # Format the results in a user-friendly way
        result = f"Search results for: {query}\n\n"

        for i, item in enumerate(data.get("organic", [])[:5], 1):
            result += f"{i}. {item.get('title', 'No title')}\n"
            result += f"   {item.get('snippet', 'No description')}\n"
            result += f"   URL: {item.get('link', 'No link')}\n\n"

        return result
