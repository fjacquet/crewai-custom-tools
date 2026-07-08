"""Tests for the auto-registered MCP server (parity with the library exports)."""

import asyncio
import json
import re

from crewai.tools import BaseTool

import crewai_custom_tools as pkg
from crewai_custom_tools.mcp_server import REGISTERED, SKIPPED, _mcp_name, mcp


def _exported_tool_count() -> int:
    return sum(
        1
        for n in pkg.__all__
        if isinstance(getattr(pkg, n, None), type)
        and issubclass(getattr(pkg, n), BaseTool)
    )


def test_mcp_registers_every_exported_tool():
    """Every exported BaseTool is on the MCP surface (full parity, nothing skipped)."""
    assert SKIPPED == []
    assert REGISTERED == _exported_tool_count()


def test_mcp_list_tools_matches_registered():
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == REGISTERED


def test_all_mcp_names_conform_to_spec():
    """MCP tool names must be [A-Za-z0-9_.-] only (no spaces from legacy display names)."""
    tools = asyncio.run(mcp.list_tools())
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+", t.name) for t in tools)


def test_slugify_examples():
    assert _mcp_name("FRED Macro Indicators Tool") == "fred_macro_indicators_tool"
    assert _mcp_name("perplexity_search") == "perplexity_search"


def test_no_arg_and_arg_schemas_are_derived():
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    # No-arg tool (FearGreedTool) → no properties.
    assert not (tools["fear_and_greed_sentiment"].inputSchema or {}).get("properties")
    # Arg tool (FREDMacroTool) → exposes its `indicator` param.
    fred_props = tools["fred_macro_indicators_tool"].inputSchema["properties"]
    assert "indicator" in fred_props


def test_invoking_a_tool_returns_the_envelope(monkeypatch):
    """Calling a registered tool routes to _run and returns the JSON envelope."""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    result = asyncio.run(
        mcp.call_tool("fred_macro_indicators_tool", {"indicator": "fed_rate"})
    )
    payload = json.loads(result[0].text)
    assert payload["success"] is False
    assert "FRED_API_KEY" in payload["error"]
