# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`crewai-custom-tools` is a **Universal Monolith** Python package (Python ≥3.11) that consolidates 30+ Pydantic-validated tools for CrewAI multi-agent systems into a single, zero-config installable library. Tools cover five domains: Web Search/Scraping, Finance/Markets, OSINT recon, Report/PDF compilation, and Enterprise integrations (Todoist, Airtable, AccuWeather, RAG). The same tools are also exposed over MCP via a FastMCP stdio server.

## Commands

This project uses **`uv`** for dependency management. There is no Makefile or task runner.

```bash
uv pip install --system -e ".[dev]"   # Install package + dev deps (what CI runs)
uv sync                                # Sync from uv.lock into .venv

python -m pytest -v                    # Run the full suite (CI command)
python -m pytest tests/test_osint_tools.py            # Single file
python -m pytest tests/test_osint_tools.py::test_github_search_success   # Single test

uv run crewai-custom-tools-mcp         # Launch the FastMCP stdio server
mkdocs build                           # Build docs site into site/ (also mkdocs serve)
python scripts/generate_sbom.py        # Regenerate sbom.json
```

CI (`.github/workflows/ci.yml`) runs `python -m pytest -v` against Python 3.11, 3.12, and 3.13 on every push/PR to `main`. Docs deploy to GitHub Pages on push to `main`.

Ruff is used for linting (`.ruff_cache/` present) but is not wired into CI — run `ruff check src tests` manually if touching style.

## Architecture

### Universal Monolith packaging (ADR-0002)
All runtime dependencies live in the single `dependencies` block of `pyproject.toml` — there are **no optional extras** for features (only `[dev]`). Any of the 30+ tools must import and run out of the box with zero `ModuleNotFoundError`. When adding a dependency, prefer pure-Python libraries and avoid C-compiled ones (e.g. no `ta-lib`/`quantlib`) so installs work in minimal Docker containers. Implement quantitative calculations with pandas/numpy fallbacks rather than C extensions.

### Tool anatomy (the pattern every tool follows)
Each tool is a `crewai.tools.BaseTool` subclass paired with a Pydantic `BaseModel` input schema:
- Class attrs: `name`, `description`, `args_schema` (points to the input model).
- Logic lives in `_run(self, ...)` and **always returns a JSON string** (`json.dumps(...)`), including on error — errors are returned as `{"error": ...}` / `{"success": False}` payloads, never raised to the agent.
- Two cross-cutting decorators from `core/` and `config/`:
  - `@api_tool(provider=..., endpoint=..., timeout=..., default_return=...)` (`core/decorators.py`) — wraps `_run` to enforce a `ThreadPoolExecutor` timeout (prevents hung agent loops), auto-retry once on HTTP 429, and convert any exception into `default_return`.
  - `@cache_api_call(key=..., ttl=...)` (`config/cache.py`) — SHA-256-keyed memory+disk cache. It strips instance `self` down to the class name so decorated methods produce deterministic keys.
- Study `tools/finance/market_data.py` and `tools/web/perplexity.py` as reference implementations before writing a new tool.

### Directory layout (`src/crewai_custom_tools/`)
- `tools/{web,finance,osint}/` — the tool implementations, grouped by domain.
- `enterprise/` — Todoist, Airtable, AccuWeather, RAG tools (same BaseTool pattern).
- `reporting/` — Jinja2 HTML renderers + WeasyPrint PDF compiler.
- `models/` — Pydantic input/output schemas, kept separate from tool logic.
- `core/decorators.py`, `config/cache.py` — the resiliency + caching infrastructure.
- `mcp_server.py` — FastMCP wrapper; each `@mcp.tool()` lazily imports the corresponding BaseTool and calls `._run()`.

### Two-surface exposure — keep them in sync
Every tool is reachable two ways, and adding a tool means touching both:
1. **Library**: exported from the top-level `src/crewai_custom_tools/__init__.py` (`__all__`) so users do `from crewai_custom_tools import XyzTool`.
2. **MCP**: registered as an `@mcp.tool()` function in `mcp_server.py`. The `[project.scripts]` entrypoint `crewai-custom-tools-mcp = "crewai_custom_tools.mcp_server:run"` is what `uv run` launches.

### Hybrid authentication (ADR-0005)
OSINT/scraper tools default to **keyless/free fallbacks** and auto-upgrade to the official paid API when the relevant env var is set (e.g. `EpieosEmailLookupTool`, `OpenCorporatesSearchTool`, `UnifiedScraperTool` escalating BeautifulSoup → ScrapeNinja → Firecrawl). Tools must degrade gracefully when a key is absent — return a keyless result or a structured error, never crash. See the API key table in `README.md` for which keys are STRICTLY REQUIRED vs OPTIONAL (fallback).

### Report templates
`reporting/html_generator.py` resolves the Jinja2 template dir as `Path(__file__).parents[3] / "templates"` (repo-root `templates/`), falling back to `./templates`. HTML report templates live in the top-level `templates/` dir, not inside the package.

## Testing conventions
- Tests are **100% offline/mocked** — the whole suite runs in seconds with no network. Use `pytest-mock`'s `mocker` fixture: `mocker.patch("requests.get", ...)` for HTTP and `mocker.patch.dict(os.environ, {...})` to inject API keys.
- New tools require a mocked success-path test and typically an error/no-key-path test; add exports to `tests/test_exports.py`.
- There is no `conftest.py` — fixtures come from `pytest-mock`. Test files are named `tests/test_<domain>_tools.py`.

## Documentation & decisions
- Architectural decisions are recorded as ADRs in `docs/adr/` — read the relevant ADR before changing packaging, MCP, auth, or deployment behavior, and add a new ADR for significant decisions.
- Design specs and plans live under `docs/superpowers/`; the SDD progress ledger is in `.superpowers/sdd/`.
- Bump `__version__` in `src/crewai_custom_tools/__init__.py` **and** `version` in `pyproject.toml` together (kept in lockstep; `tests/test_scaffold.py` asserts the value).
