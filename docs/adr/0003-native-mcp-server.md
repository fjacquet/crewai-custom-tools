# ADR 0003: Native Model Context Protocol (MCP) Server Integration

**Date**: 2026-07-05
**Author**: Gemini CLI & Collaborative Engineering Team
**Status**: ACCEPTED

---

## Context & Problem Statement

While `crewai-custom-tools` was initially designed as a local Python library to be imported directly inside CrewAI multi-agent scripts, modern developers frequently use AI-native code editors (such as Cursor or Windsurf) and chat assistants (such as Claude Desktop). These clients natively support the Model Context Protocol (MCP) to interact with local filesystems, networks, and APIs.

We needed a standardized way to expose our unified, resilient search, stock, crypto, and reporting tools to external LLM clients without requiring them to execute custom Python orchestration files.

---

## Considered Alternatives

1. **Require Custom Local Client Scripts**: Force users to write custom Python wrappers for every editor.
   - *Verdict*: Rejected. High friction; breaks interoperability and isolates the tools from non-Python execution environments.
2. **Integrate FastMCP stdio Server** [Chosen]: Create a centralized, lightweight MCP server using Anthropic's official `FastMCP` SDK, exposing the primary tools over standard input/output (stdio) channels, and register it as a global terminal command in `pyproject.toml`.

---

## Architectural Decisions

- **Centralized MCP Server (`mcp_server.py`)**: Implement `src/crewai_custom_tools/mcp_server.py` using `FastMCP("crewai-custom-tools")`. Expose key tools as standard MCP functions (e.g., `search_perplexity`, `search_google`, `get_stock_metrics`, `search_french_business_registry`, `compile_html_to_pdf`).
- **Global Console Script**: Add `crewai-custom-tools-mcp` under `[project.scripts]` inside `pyproject.toml`, compiling it as a globally executable terminal command when installed.

---

## Implications & Consequences

- **Universal Editor Interoperability**: Downstream users can natively connect our tools directly to Cursor, Windsurf, or Claude Desktop simply by specifying the local executable command `crewai-custom-tools-mcp`.
- **Decoupled Execution**: Exposes the same resilient, cached backend tools to external models even if they are not running within a CrewAI Python script.
