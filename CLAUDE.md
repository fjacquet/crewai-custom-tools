# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`crewai-custom-tools` is a **Universal Monolith** Python package (Python ≥3.11) that centralizes **119 Pydantic-validated tools** for CrewAI multi-agent systems — ported from three source repos (`finwiz`, `osint_tools`, `epic_news`) — into a single, zero-config installable library. Tools cover six domains: Web Search/Scraping, Finance/Markets, OSINT recon, Report/PDF compilation, Enterprise integrations, and Files. Every tool returns a uniform `ToolResult` JSON envelope, and all tools are exposed over MCP via a FastMCP stdio server (full parity, auto-registered).

## Commands

This project uses **`uv`** for dependency management. There is no Makefile or task runner.

```bash
uv pip install --system -e ".[dev]"   # Install package + dev deps (what CI runs)
uv sync                                # Sync from uv.lock into .venv

uv run pytest -q                       # Run the full suite locally
uv run pytest tests/test_osint_tools.py               # Single file
uv run pytest tests/test_osint_tools.py::test_github_search_success   # Single test
# Bare `python` is NOT on PATH locally — use `uv run` (or .venv/bin/python).
# CI can use `python -m pytest -v` because it installs with `uv pip install --system`.

uv run crewai-custom-tools-mcp         # Launch the FastMCP stdio server
mkdocs build                           # Build docs site into site/ (also mkdocs serve)
python scripts/generate_sbom.py        # Regenerate sbom.json
```

CI (`.github/workflows/ci.yml`) runs `python -m pytest -v` against Python 3.11, 3.12, and 3.13 on every push/PR to `main`. Docs deploy to GitHub Pages on push to `main`.

Ruff runs in CI as its own `lint` job (`ruff check src tests`, must be clean) and ships in `[dev]`, so `uv run ruff check src tests` locally uses the same version. `models/__init__.py` and `models/reports/__init__.py` ignore `F403` via `[tool.ruff.lint.per-file-ignores]` — they are pure re-export aggregators.

## Architecture

### Universal Monolith packaging (ADR-0002)
All runtime dependencies live in the single `dependencies` block of `pyproject.toml` — there are **no optional extras** for features (only `[dev]`). Any of the 119 tools must import and run out of the box with zero `ModuleNotFoundError`. When adding a dependency, prefer pure-Python libraries and avoid C-compiled ones (e.g. no `ta-lib`/`quantlib`) so installs work in minimal Docker containers. Implement quantitative calculations with pandas/numpy fallbacks rather than C extensions.

### Tool anatomy (the pattern every tool follows)
Each tool is a `crewai.tools.BaseTool` subclass paired with a Pydantic `BaseModel` input schema:
- Class attrs: `name`, `description`, `args_schema` (points to the input model).
- Logic lives in `_run(self, ...)` and **always returns the `ToolResult` envelope as a JSON string** via `ok(data)` / `err("msg")` from `core/results.py` — shape `{"success", "data", "error"}`. Never raise to the agent; a failure is `err(...)` (or is caught by `@api_tool`). This uniform contract is what lets a caller tell a real failure from an empty-but-successful result. An empty-but-valid result (no news, no matches) is `ok(...)` with empty data, **not** `err`.
- Cross-cutting infrastructure:
  - `core/results.py` — the `ToolResult` envelope + `ok()`/`err()` helpers (import these in every tool).
  - `@api_tool(provider=..., endpoint=..., timeout=...)` (`core/decorators.py`) — wraps `_run` with a `ThreadPoolExecutor` timeout (prevents hung agent loops), one HTTP-429 retry, and converts any exception into an `err(...)` envelope. Tools must still set their own per-request `requests` timeout.
  - `core/cli_runner.py` — hardened no-shell subprocess runner (target validation, PATH check, timeout, output cap) behind the CLI OSINT tools (`SherlockTool`, `MaigretTool`, `TheHarvesterTool`, `NetReconTool`); they return `err("<binary> not installed")` when the binary is absent.
  - `config/cache.py` — SHA-256-keyed memory+disk cache (`@cache_api_call` / `get_cache_manager`), currently used by the Yahoo Finance tools.
- Study `tools/finance/market_data.py` and `tools/web/perplexity.py` as reference implementations before writing a new tool.

### Directory layout (`src/crewai_custom_tools/`)
- `tools/{web,finance,osint}/` — the tool implementations, grouped by domain.
- `tools/genealogy/` — the Gramps/genealogy domain, consumed by the sibling `genecrew` project: `gramps/` (httpx+JWT client, read tools + write tools `GrampsUpdateNameTool`/`GrampsUpdateGenderTool`), `models/` (generated from the Gramps OpenAPI + hand-written `domain.py`, incl. the `Proposition` model), `analysis/` (pure consistency rules R1–R10 + D1–D3, a duplicate finder, and gender inference `gender.py` — no I/O, imported by module path), `standardize/` (name casing). The prénom→sexe reference table (INSEE+OFS, ~85 500 names) ships in `data/prenoms_sexe.csv`, regenerated by `scripts/build_prenoms_sexe.py` (which auto-downloads its sources). Only `BaseTool` subclasses go in `__all__`; the pure functions do not.
- `enterprise/` — Todoist, Airtable, AccuWeather, RAG tools (same BaseTool pattern).
- `reporting/` — Jinja2 HTML renderers + WeasyPrint PDF compiler.
- `models/` — Pydantic input/output schemas, kept separate from tool logic.
- `core/decorators.py`, `config/cache.py` — the resiliency + caching infrastructure.
- `core/results.py`, `core/decorators.py`, `core/cli_runner.py`, `config/cache.py` — the envelope + resiliency + subprocess + caching infrastructure.
- `mcp_server.py` — FastMCP wrapper that **auto-registers every exported tool** from `__all__`, deriving each MCP tool's params from the tool's `args_schema`.

### Gramps data notes (for genealogy tools)
- Fetch people efficiently: `GET /api/people/?profile=all&extend=event_ref_list` returns human strings + citation counts (`profile`) AND raw dates (`extended.events`) in one call per page.
- Dates: compare via the integer `sortval` (Julian day; `0` = unknown/unsortable). Undated events come back as `dateval=[0,0,0,False]`, `year=0`, `sortval=0` (not empty). Text-only dates have `modifier==6`; `quality` valid 0–2, `modifier` valid 0–6. Gender int: `0=F, 1=M, 2=U`.
- Write policy: casing = *form* → direct write OK, guarded by a case-only invariant (`is_case_only_change`, which refuses any non-casing change incl. whitespace). A *fact* needs a source → proposal — **except gender**, written at high confidence by `GrampsUpdateGenderTool` (ADR 0009, in the genecrew repo). Writes are gated by the per-call `dry_run` param OR the global `GENECREW_DRY_RUN` env switch (the env can only *force* simulation).

### Two-surface exposure
Every tool is reachable two ways:
1. **Library**: export it from `src/crewai_custom_tools/__init__.py` (`__all__`) so users do `from crewai_custom_tools import XyzTool`. **This is the only registration step.**
2. **MCP**: `mcp_server.py` auto-registers everything in `__all__`, so a new library export appears in MCP automatically (no per-tool wrapper). The `[project.scripts]` entrypoint `crewai-custom-tools-mcp = "crewai_custom_tools.mcp_server:run"` launches it.

Forgetting the export is silent: the tool is absent from *both* surfaces, and nothing fails — 15 tools drifted this way between 0.13.0 and 0.17.0, because `genecrew` imports genealogy tools by full module path and never noticed. `tests/test_export_surface.py` now enforces it: every defined `BaseTool` subclass must be in `__all__`, and `register_all()` must skip nothing.

### Hybrid authentication (ADR-0005)
OSINT/scraper tools default to **keyless/free fallbacks** and auto-upgrade to the official paid API when the relevant env var is set (e.g. `EpieosEmailLookupTool`, `OpenCorporatesSearchTool`, `UnifiedScraperTool` escalating BeautifulSoup → ScrapeNinja → Firecrawl). Tools must degrade gracefully when a key is absent — return a keyless result or a structured error, never crash. See the API key table in `README.md` for which keys are STRICTLY REQUIRED vs OPTIONAL (fallback).

### Report templates
HTML templates live **inside the package** at `reporting/templates/` and are resolved via `Path(__file__).parent / "templates"` (`default_template_dir()` in `html_generator.py`), so they ship in the wheel and work on a plain `pip install`. Reporting tools share `build_environment()`; untrusted section content is escaped (`_sections_to_html`) — do not reintroduce `| safe` on agent-supplied content.

## Testing conventions
- **739 tests, 100% offline/mocked** — the whole suite runs in seconds with no network. Use `pytest-mock`'s `mocker`: `mocker.patch("requests.get", ...)` for HTTP and `mocker.patch.dict(os.environ, {...})` for keys. Assert on the envelope (`json.loads(result)["success"]`), not on prose strings.
- New tools require a mocked success-path test and an error/no-key-path test (asserting `success is False`), plus the export in `__all__`.
- There is no `conftest.py` — fixtures come from `pytest-mock`. Test files live under `tests/` per domain (e.g. `test_finance_tools.py`, `test_search_providers.py`).

## Documentation & decisions
- Architectural decisions are recorded as ADRs in `docs/adr/` — read the relevant ADR before changing packaging, MCP, auth, or deployment behavior, and add a new ADR for significant decisions.
- Design specs and plans live under `docs/superpowers/`; the SDD progress ledger is in `.superpowers/sdd/`.
- Bump `__version__` in `src/crewai_custom_tools/__init__.py` **and** `version` in `pyproject.toml` together — `tests/test_scaffold.py` compares the two sources, so they cannot drift silently (they did, 0.12.0→0.16.0, when the test still asserted a hardcoded literal).
- Releasing is not done until the tag exists: bump both versions → CHANGELOG entry → `git tag -a vX.Y.Z` → `gh release create`. Five versions shipped to `main` untagged before this was written.
