"""Perplexity Sonar tool with optional JSON-schema structured output."""

import json
import os
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
_DEFAULT_SYSTEM = (
    "You are a research assistant. Provide concise, evidence-grounded answers with citations."
)


class PerplexityStructuredInput(BaseModel):
    """Input schema for PerplexityStructuredTool."""

    prompt: str = Field(..., description="The research prompt / question.")
    json_schema: Optional[dict] = Field(
        None,
        description="Optional JSON Schema; when provided, the model is asked to return "
        "JSON matching it (response_format=json_schema) and the parsed object is returned.",
    )
    model: str = Field("sonar-pro", description="Perplexity model id.")
    recency: Optional[str] = Field(
        "month", description="search_recency_filter: hour|day|week|month|year or null."
    )


class PerplexityStructuredTool(BaseTool):
    """Query Perplexity Sonar, optionally constraining the answer to a JSON schema."""

    name: str = "perplexity_structured"
    description: str = (
        "Runs a Perplexity Sonar research query. If a json_schema is supplied, the answer "
        "is returned as a parsed JSON object matching that schema; otherwise as text with "
        "citations. Requires PERPLEXITY_API_KEY."
    )
    args_schema: type[BaseModel] = PerplexityStructuredInput

    @api_tool(provider="Perplexity", endpoint="StructuredSearch", timeout=60.0)
    def _run(
        self,
        prompt: str,
        json_schema: Optional[dict] = None,
        model: str = "sonar-pro",
        recency: Optional[str] = "month",
    ) -> str:
        """Call Perplexity Sonar and return content (structured when a schema is given)."""
        api_key = os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY")
        if not api_key:
            return err("PERPLEXITY_API_KEY not configured")

        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": _DEFAULT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "return_citations": True,
        }
        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"schema": json_schema},
            }
        if recency:
            payload["search_recency_filter"] = recency

        resp = requests.post(
            _PERPLEXITY_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        content = (
            data.get("choices", [{}])[0].get("message", {}).get("content")
            if data.get("choices")
            else None
        )
        if content is None:
            return err("Perplexity response missing content")

        citations = data.get("citations", [])
        if json_schema:
            try:
                return ok({"structured": json.loads(content), "citations": citations})
            except (json.JSONDecodeError, TypeError):
                # Model didn't return valid JSON — surface the raw content honestly.
                return ok({"content": content, "citations": citations, "schema_parsed": False})
        return ok({"content": content, "citations": citations})
