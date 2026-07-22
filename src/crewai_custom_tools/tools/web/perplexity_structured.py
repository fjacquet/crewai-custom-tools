"""Perplexity Sonar tool with optional JSON-schema structured output."""

import json
import logging
import os
from typing import Optional

import httpx
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.keys import require_api_key
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)

_PERPLEXITY_URL = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai/chat/completions")
_DEFAULT_SYSTEM = (
    "You are a research assistant. Provide concise, evidence-grounded answers with citations."
)


class PerplexityStructuredInput(BaseModel):
    """Input schema for PerplexityStructuredTool."""

    prompt: str = Field(..., description="The research prompt / question.")
    json_schema: dict | None = Field(
        None,
        description="Optional JSON Schema; when provided, the model is asked to return "
        "JSON matching it (response_format=json_schema) and the parsed object is returned.",
    )
    model: str = Field("sonar-pro", description="Perplexity model id.")
    recency: str | None = Field(
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
        json_schema: dict | None = None,
        model: str = "sonar-pro",
        recency: str | None = "month",
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


_DEFAULT_STRUCTURED_SYSTEM = (
    "You are a research assistant. Provide concise, evidence-grounded answers with citations."
)


async def perplexity_structured[T: BaseModel](
    *,
    prompt: str,
    schema: type[T],
    system: str = _DEFAULT_STRUCTURED_SYSTEM,
    model: str = "sonar-pro",
    search_recency_filter: str | None = "month",
    timeout: float = 60.0,
    api_key: str | None = None,
) -> T | None:
    """Call Perplexity Sonar with JSON-schema structured output.

    Returns a validated ``schema`` instance, or ``None`` if the call or parse
    failed (callers treat research as best-effort). Raises ``ValueError`` when
    no API key is configured.
    """
    key = api_key or require_api_key("PERPLEXITY_API_KEY", "PPLX_API_KEY", tool_name="perplexity_structured")
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": schema.model_json_schema()},
        },
        "return_citations": True,
    }
    if search_recency_filter:
        payload["search_recency_filter"] = search_recency_filter

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(_PERPLEXITY_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(f"Perplexity HTTP {exc.response.status_code} for {schema.__name__}")
        return None
    except (TimeoutError, httpx.HTTPError) as exc:
        logger.warning(f"Perplexity transport error for {schema.__name__}: {exc}")
        return None
    except ValueError as exc:
        logger.warning(f"Perplexity returned non-JSON for {schema.__name__}: {exc}")
        return None

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.warning(f"Perplexity response missing content for {schema.__name__}")
        return None

    try:
        return schema.model_validate_json(content)
    except ValidationError:
        try:
            return schema.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(f"Perplexity output unrecoverable for {schema.__name__}: {exc}")
            return None
