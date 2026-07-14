"""Shared test configuration for the central tools suite."""

import os

# Rate limiting is exercised explicitly in test_rate_limiter.py; everywhere
# else it must never slow a test down or make timing flaky.
os.environ.setdefault("CREWAI_TOOLS_RATE_LIMIT_DISABLED", "1")

# PerplexitySearchTool fails fast (ValueError) without a key. Tools that
# instantiate every exported BaseTool (e.g. the MCP server's module-level
# register_all() in mcp_server.py) need a key present *before* that import
# runs, which happens at collection time — too early for a per-test
# monkeypatch fixture. setdefault() is a no-op when a real key is already
# configured (e.g. via a developer's own environment), and tests that
# specifically exercise the no-key path (test_perplexity.py, the
# HybridSearchTool cascade tests) clear/delete it explicitly per-test.
os.environ.setdefault("PERPLEXITY_API_KEY", "test-key")
