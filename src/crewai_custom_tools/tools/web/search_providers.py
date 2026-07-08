"""Additional web-search provider tools: Brave, Tavily, SerpApi, and a hybrid cascade."""

import json
import logging
import os
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


class _SearchQueryInput(BaseModel):
    """Input schema for single-query search tools."""

    query: str = Field(..., description="The search query to execute.")


class BraveSearchInput(BaseModel):
    """Input schema for the Brave Search tool."""

    query: str = Field(..., description="The search query to execute.")
    count: int = Field(10, description="Maximum number of results to return.")
    country: Optional[str] = Field(None, description="Optional country code (e.g. 'US', 'FR').")


class BraveSearchTool(BaseTool):
    """Web search via the Brave Search API (reliable, current links)."""

    name: str = "brave_search"
    description: str = (
        "Search the web using the Brave Search API. Returns titles, URLs, and snippets. "
        "Requires the BRAVE_API_KEY environment variable."
    )
    args_schema: type[BaseModel] = BraveSearchInput

    @api_tool(provider="Brave", endpoint="Search")
    def _run(self, query: str, count: int = 10, country: Optional[str] = None) -> str:
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            return err("BRAVE_API_KEY not configured")
        params = {"q": query, "count": count}
        if country:
            params["country"] = country
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        web_results = response.json().get("web", {}).get("results", [])
        results = [
            {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("description", "")}
            for r in web_results[:count]
        ]
        return ok({"query": query, "results": results})


class TavilyTool(BaseTool):
    """AI web search via the Tavily API."""

    name: str = "tavily_search"
    description: str = (
        "Search the web using the Tavily API, returning relevant results (and an optional "
        "synthesized answer) for a query. Requires the TAVILY_API_KEY environment variable."
    )
    args_schema: type[BaseModel] = _SearchQueryInput

    @api_tool(provider="Tavily", endpoint="Search")
    def _run(self, query: str) -> str:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return err("TAVILY_API_KEY not configured")
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        results = [
            {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content", "")}
            for r in data.get("results", [])
        ]
        return ok({"query": query, "results": results, "answer": data.get("answer")})


class SerpApiInput(BaseModel):
    """Input schema for the SerpApi search tool."""

    query: str = Field(..., description="The search query.")
    num_results: int = Field(5, description="Number of results to return (1-10).")
    country: str = Field("us", description="Country code for localized results (e.g. 'us', 'uk').")
    language: str = Field("en", description="Language code (e.g. 'en', 'fr').")


class SerpApiTool(BaseTool):
    """Web search via SerpApi (serpapi.com) — distinct from the Serper.dev tool."""

    name: str = "serpapi_search"
    description: str = (
        "Search the web using SerpApi (serpapi.com). Requires the SERPAPI_API_KEY environment "
        "variable. Distinct from the Serper.dev search tool."
    )
    args_schema: type[BaseModel] = SerpApiInput

    @api_tool(provider="SerpApi", endpoint="Search")
    def _run(
        self, query: str, num_results: int = 5, country: str = "us", language: str = "en"
    ) -> str:
        if not query or len(query.strip()) < 2:
            return err("Search query must be at least 2 characters")
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return err("SERPAPI_API_KEY not configured")
        response = requests.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": api_key,
                "num": num_results,
                "hl": language,
                "gl": country,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            return err(f"SerpApi error: {data['error']}")
        results = [
            {"title": i.get("title"), "link": i.get("link", ""), "snippet": i.get("snippet", "")}
            for i in data.get("organic_results", [])[:num_results]
        ]
        return ok({"query": query, "results": results, "count": len(results)})


class HybridSearchTool(BaseTool):
    """Cascading web search: Perplexity -> Brave -> Serper (first success wins)."""

    name: str = "hybrid_search"
    description: str = (
        "Resilient web search that tries Perplexity (AI synthesis), then Brave, then Serper, "
        "returning the first provider that succeeds. Uses whichever API keys are configured."
    )
    args_schema: type[BaseModel] = _SearchQueryInput

    @api_tool(provider="HybridSearch", endpoint="Search")
    def _run(self, query: str) -> str:
        from crewai_custom_tools.tools.web.perplexity import PerplexitySearchTool
        from crewai_custom_tools.tools.web.serper import SerperSearchTool

        providers = [
            ("perplexity", PerplexitySearchTool()),
            ("brave", BraveSearchTool()),
            ("serper", SerperSearchTool()),
        ]
        errors = []
        for name, tool in providers:
            payload = json.loads(tool._run(query))
            if payload.get("success") and payload.get("data"):
                return ok({"query": query, "provider": name, "results": payload["data"]})
            errors.append(f"{name}: {payload.get('error')}")
        return err(f"All search providers failed: {'; '.join(errors)}")
