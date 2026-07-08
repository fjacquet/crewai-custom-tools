"""Perplexity AI-powered search tool."""

import logging
import os

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


class PerplexitySearchInput(BaseModel):
    """Input schema for Perplexity Search Tool."""

    query: str = Field(..., description="The search query")
    focus: str = Field(
        "internet",
        description=(
            "Search focus: 'internet' (default web search), 'academic' (scholarly "
            "sources), or 'reddit' (restricted to reddit.com)."
        ),
    )
    recency: str = Field("week", description="Recency filter: day, week, month")


# Focus modes mapped to the Perplexity request parameters we can actually honor.
# 'internet' (and anything unrecognized) is the plain default with no extra params.
_FOCUS_PARAMS = {
    "academic": {"search_mode": "academic"},
    "reddit": {"search_domain_filter": ["reddit.com"]},
}


class PerplexitySearchTool(BaseTool):
    """AI-powered web search with synthesis and citations."""

    name: str = "perplexity_search"
    description: str = (
        "AI-powered web search using Perplexity API. Returns synthesized answers "
        "with citations. Supports focus modes: 'internet' (default), 'academic', 'reddit'."
    )
    args_schema: type[BaseModel] = PerplexitySearchInput

    @api_tool(provider="Perplexity", endpoint="Search")
    def _run(self, query: str, focus: str = "internet", recency: str = "week") -> str:
        """Execute a Perplexity search and return a synthesized answer with citations."""
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            return err("PERPLEXITY_API_KEY not configured")

        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
            "search_recency_filter": recency,
        }
        payload.update(_FOCUS_PARAMS.get(focus, {}))

        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        # Guard the parse — a 200 with an unexpected body must not raise to the agent.
        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        answer = message.get("content")
        if not answer:
            return err("Perplexity returned no answer content")

        return ok(
            {
                "answer": answer,
                "citations": data.get("citations", []),
                "source": "perplexity",
            }
        )
