# Proper Centralization & Correctness Plan

**Date:** 2026-07-08
**Branch:** `feat/proper-centralization`
**Status:** COMPLETE (2026-07-08)

## Final outcome
- Phase 0 (foundation), Phase 1 (37 existing tools fixed), Phase 2 (41 new tools
  centralized), Phase 3 (MCP parity, docs, v0.2.0) — all done.
- **81 tool classes** exported; **207 tests** green; MCP exposes all 81.
- **Deferred** (too app-coupled to port cleanly — recommend fresh clean rebuilds):
  `MarketScreeningTool`, `StandardizedSentimentAnalysisTool`,
  `CrossAssetSentimentComparatorTool`, `EnhancedSECAnalysisTool`,
  `StandardizedRiskScoringTool` (finwiz); `HtmlGeneratorTool` (epic_news crew renderer).
- **Follow-ups:** `menu_report_template.html` still has a `{{ | safe }}` for a future
  menu tool; broaden `@cache_api_call` usage to more idempotent GET tools if desired.

## Goal

Turn `crewai-custom-tools` into a *correct*, *complete*, and *trustworthy* centralization of
the CrewAI tools that live across three authoritative source repos:

- `~/Projects/finwiz` — finance (`src/finwiz/tools/`)
- `~/Projects/osint_tools` — OSINT (`src/osint_tools/providers/` + `infra/`)
- `~/Projects/crews/epic_news` — web + enterprise + reporting + finance (`src/epic_news/tools/`)

Two axes of work:
1. **Fix** all ~37 currently-centralized tools (a full review on 2026-07-08 found ~50 defects).
2. **Centralize** the ~45 genuinely-reusable tools that were never ported.

## Key insight from the source-repo survey

For most findings, **the source repos are broken the same way** — the ports faithfully copied
pre-existing bugs. So this is a genuine correctness pass, not a copy job. Only three findings are
true regressions where the source is correct and can be lifted directly:

- `SaveToRagTool` — epic_news returns `status:"error"` on failure; the port changed it to `success`.
- `SerperEmailSearchTool` query string — epic_news has the balanced-quote version.
- `WikipediaArticleTool.get_sections` — epic_news uses the library's `page.sections` property.

Correct reference implementations that DO exist upstream:
- ETF holdings via `yf.Ticker(t).get_funds_data().top_holdings` — `finwiz/src/finwiz/discovery/universe_provider.py:122-156`.
- Perplexity resilience shape — `finwiz/src/finwiz/tools/perplexity_search_tool.py` (`@api_tool`, returns full payload, never indexes `choices[0]`).
- History %-change — `finwiz/src/finwiz/tools/yahoo_finance_history_tool.py:85` (divide by real earliest close).
- Reporting content-build+inject — `epic_news/src/epic_news/tools/utils/html/template_renderers/*` + `template_manager.py`.

No upstream fix exists for: yfinance news `content.*` keys, Fear&Greed CNN keys, RDAP public-suffix
split, personne-morale officers, OpenCorporates/Epieos keyless behavior — all written fresh.

## Decisions (2026-07-08)

- **Scope:** fix existing AND centralize everything missing (~82 tools touched/created total).
- **Username detection:** in-Python heuristic (no `sherlock`/`maigret` binary dependency). Treat
  403/429/5xx as `unknown`, add per-site negative-body markers, check platforms concurrently.
- **Return contract:** adopt a `ToolResult` envelope — every `_run` returns
  `{"success": bool, "data": <any>|null, "error": <str>|null}` as a JSON string via
  `core/results.py` `ok()` / `err()` helpers.
- **Style constraints:** uv, pytest, KISS, DRY, functional. Small pure helpers over stateful classes;
  no duplication; no over-engineering.

## Foundational design

### `core/results.py` (DONE)
`ToolResult` frozen dataclass + `ok(data)` / `err(message, data=None)` pure helpers returning the
canonical JSON string. Every tool adopts this.

### `core/decorators.py` `@api_tool` rework
- On any failure (timeout / HTTPError / exception) return `err(f"{provider} {endpoint}: {e}")`
  instead of the current empty `default_return` (`"{}"`/`"[]"`), so failure is always
  distinguishable and JSON-shaped (fixes S1).
- Drop the `default_return` empty-shape param (or default it to the error envelope).
- Require inner per-request `requests` timeouts in tools so the abandoned-thread window is bounded (S4).

### Template packaging (H1)
Move `templates/` → `src/crewai_custom_tools/reporting/templates/`, load via
`importlib.resources`, and include as package data in `pyproject.toml`
(`[tool.hatch.build.targets.wheel.force-include]` or package-data). Fix resolvers in
`html_generator.py` and `template_renderers.py`. Add a test that renders after a wheel-style install.

## Phased roadmap

### Phase 0 — Foundation ✅ DONE (commit 9e90923)
- [x] Create branch, `core/results.py`, this plan.
- [x] Rework `@api_tool` to the error envelope; update `tests/test_decorators.py`.
- [x] Package templates properly; fix resolvers; packaging test (verified in built wheel).
- [x] Green baseline: full `pytest` passes on the reworked foundation.

### Phase 1 — Fix existing tools (envelope + per-tool defects) ✅ DONE
Committed per domain: finance (bbde848), web (06db04c), osint (0aa60fc),
reporting (e463555), enterprise (ddbe527). Full suite green (121 passed).
Convert each tool to `ok()/err()` and fix its specific findings. By domain:
- **Web:** perplexity (wire or drop `focus`, guard parse, `@api_tool`, read key in `_run`);
  serper (only `SERPER_API_KEY`); scraper (firecrawl SDK object, uniform schema, `title` default);
  wikipedia (`page.sections`, JSON everywhere); rss (OPML→JSON, UTC-aware dates);
  fact_checking (`json.dumps`).
- **Finance:** ETF (`get_funds_data()`), news (`content.*` keys), history (%-change),
  ticker/company (restore beta/ROE/D-E where cheap), crypto (CMC env primary, Kraken JSON,
  drop/impl `asset_class`), fear_greed (CNN `fear_and_greed.score/.rating`, add `args_schema`),
  exchange_rate (JSON).
- **OSINT:** username (heuristic), email (serper query, epieos keyless→explicit unavailable,
  holehe surface rate-limited/errors, URL-encode), domain (RDAP `tldextract`), registers
  (personne-morale `denomination` branch), corporate (OpenCorporates surface auth error),
  github (`.get()` indexing, org `exists`/`top_repos` correctness).
- **Reporting:** fix Pestel/Financial renderers (supply the template context they need, or adopt
  the content-build+inject design), remove `{{ ... | safe }}` XSS (or sanitize).
- **Enterprise:** accuweather `https`, airtable (URL-encode, reject empty `data`), todoist
  (parse body once), rag (port correct failure handling from epic_news).

### Phase 2 — Centralize missing tools (~45)
Group + register in `__init__.py` `__all__` and the MCP server.
- **epic_news:** Brave/Tavily/SerpApi/Hybrid search; standalone ScrapeNinja/Firecrawl/BatchArticleScraper;
  CoinMarketCap list/news/historical; Geoapify; TechStack; data-centric (Metrics/KPI/DataViz/StructuredReport);
  HtmlGeneratorTool + TemplateManager pipeline; UniversalReport/Reporting; RSSFeed/UnifiedRss;
  WikipediaProcessing; DelegatingEmailSearch.
- **finwiz:** EnhancedETF, EnhancedCrypto, DeFiMetrics, TwelveData (+multi), AVNewsSentiment,
  EnhancedSEC, MarketScreening, TickerValidation, Sentiment (+cross-asset), ChartImg, PerplexityStructured.
- **osint_tools:** maigret, theHarvester, sherlock (optional — needs CLI), INSEE Sirene, BODACC,
  net_recon, GDELT, Google News RSS, Hunter find/verify. NOTE: CLI-backed ones need a decision
  (port `cli_runner` vs skip); HTTP ones port cleanly with the envelope.

### Phase 3 — Docs, tests, verification
- Port/adapt source tests (epic_news `tests/tools/`, finwiz `tests/unit/tools/`, osint_tools
  `tests/providers/`) — mock the single network/CLI boundary.
- Fix README (test count 87→actual; caching claim; MCP subset note); regenerate CLAUDE.md;
  bump `__version__` + `pyproject` version together; regenerate `sbom.json`.
- Full `pytest` green; add a MCP parity check; `verify` the reporting/render path end-to-end.

## Testing strategy
- Offline/mocked (`pytest-mock`); mock the single network boundary per tool.
- Every fixed tool gets a success-path + failure-path (envelope `success:false`) test.
- Adopt source fixtures where they exist; author fresh tests for the fresh fixes.

## Risks
- Envelope change touches every tool + all 91 existing tests → do it behind the `@api_tool` rework
  first, then migrate domain-by-domain to keep the suite green incrementally.
- Some ⚠️ finance/OSINT fixes depend on live API/library behavior (yfinance `funds_data`, CNN keys,
  OpenCorporates auth) → verify against the installed libs / a live probe before finalizing.
- CLI-backed OSINT tools (sherlock/maigret/theHarvester/net_recon) conflict with the zero-dep
  install ethos → gate behind availability checks; treat binaries as optional.
