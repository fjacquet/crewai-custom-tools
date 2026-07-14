"""Perplexity AI-powered search tool."""

import logging
import os
from typing import Any

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.keys import require_api_key
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)

_PERPLEXITY_URL = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai/chat/completions")


class PerplexitySearchInput(BaseModel):
    """Input schema for Perplexity Search Tool."""

    query: str = Field(..., description="Natural language query to research with Perplexity Sonar.")
    model: str = Field("sonar-pro", description="Perplexity model to use (e.g., sonar-pro).")
    top_k: int | None = Field(5, description="Maximum number of web results to retrieve (1-10 typical).")
    search_recency: str | None = Field(
        None, description="Recency filter: 'hour', 'day', 'week', 'month', or 'year'. Empty for default."
    )
    search_domain_filter: list[str] | None = Field(
        None, description="Restrict the search to these domains, e.g. ['reddit.com']."
    )


class PerplexitySearchTool(BaseTool):
    """AI-powered web search with synthesis and citations."""

    name: str = "perplexity_search"
    description: str = (
        "AI-powered web search using Perplexity API. Returns synthesized answers "
        "with citations. Requires PERPLEXITY_API_KEY (or legacy PPLX_API_KEY)."
    )
    args_schema: type[BaseModel] = PerplexitySearchInput

    def model_post_init(self, __context: Any) -> None:
        """Validate the API key at instantiation (fail-fast)."""
        super().model_post_init(__context)
        self._api_key = require_api_key("PERPLEXITY_API_KEY", "PPLX_API_KEY", tool_name=type(self).__name__)

    @api_tool(provider="Perplexity", endpoint="Search", timeout=45.0)
    def _run(
        self,
        query: str,
        model: str = "sonar-pro",
        top_k: int | None = 5,
        search_recency: str | None = None,
        search_domain_filter: list[str] | None = None,
    ) -> str:
        """Execute a Perplexity search and return a synthesized answer with citations."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": query}],
            "return_citations": True,
        }
        if top_k is not None:
            payload["top_k"] = top_k
        if search_recency:
            payload["search_recency_filter"] = search_recency
        if search_domain_filter:
            payload["search_domain_filter"] = search_domain_filter

        response = requests.post(
            _PERPLEXITY_URL,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        answer = message.get("content")
        if not answer:
            return err("Perplexity returned no answer content")

        return ok({"answer": answer, "citations": data.get("citations", []), "source": "perplexity"})
