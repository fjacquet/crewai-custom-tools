# Changelog

All notable changes to the `crewai-custom-tools` project will be documented in this file.

---

## [0.6.1] - 2026-07-16

### Fixed

- `mkdocs.yml` nav referenced two spec/plan files with a filename typo (`crewai-custom-tools-universal-monolith*` instead of the actual `crew-custom-tools-universal-monolith*`), which aborted `mkdocs build --strict`. Also added 3 previously-orphaned docs pages (OSINTFR plan/spec, the 2026-07-08 centralization plan) to the nav.
- Refreshed stale counts/links left over from the wave3-analytics merge: tool count (87→93, plus the new Files category) and test count (224→423) in `README.md` and `CLAUDE.md`; release version references (v0.1.1→v0.6.0) in `README.md` and `docs/USER_GUIDE.md`.

### Changed

- Refreshed `uv.lock` transitive dependency versions (e.g. `anyio` 4.14.1→4.14.2, `cffi` 2.0.0→2.1.0); `pyproject.toml` unchanged.

---

## [0.6.0] - 2026-07-15

### Added

- New `tools/files/` surface: `FileReadTool` / `DirectoryReadTool`, ported from finwiz. Deliberate exception to the package-wide `ok()`/`err()` JSON envelope — both return **plain strings** (the file/listing content an agent reads), not the standard envelope.
- New `tools/analytics/` surface: `ValuationTool`, `ETFAnalysisTool`, `RegulatoryComplianceTool`, `PositionSizingTool`, `PriceTargetCalculator`, `APlusScoringTool`, `APlusScreeningTool`. All are pure computation over caller-supplied or static-lookup-table data — none call yfinance or any other network API, so none carry the `@api_tool` rate-limit decorator used by network-backed tools elsewhere in this package.
  - `PositionSizingTool` and `PriceTargetCalculator` are **plain classes**, not `BaseTool` subclasses — they're programmatic APIs for callers like finwiz's rebalancing crew (returning typed pydantic models directly) and are therefore exported but do **not** register on the MCP tool surface. `ValuationTool`, `ETFAnalysisTool`, `RegulatoryComplianceTool`, `APlusScoringTool`, and `APlusScreeningTool` are `BaseTool`s and register automatically.
  - `APlusScreeningTool` is finwiz's `MarketScreeningTool` **renamed** (MCP/tool name `"aplus_screening"`) to avoid colliding with this package's pre-existing, simpler `tools/finance/screening.py::MarketScreeningTool` (tool name `"market_screening"`).

### Fixed

- `composite_score` fallback bug: finwiz's raw score dict put the composite score only under `analysis_summary.composite_score`, but downstream consumers (e.g. `ScreeningRanking`) read `score_result.get("composite_score", 0.5)` at the top level — silently defaulting every candidate to 0.5. `APlusScoringTool` now also emits `composite_score` at the top level of its result, alongside the existing nested copy.

---

## [0.5.1] - 2026-07-15

### Added

- `AlphaVantageOverviewTool` payload gains `sector`/`industry`/`market_cap`/`eps`/`revenue_ttm`/`description`; `EnhancedCryptoAnalysisTool` payload gains `volume_24h` (`current_price_usd`/`market_cap_usd`/`circulating_supply`/`total_supply`/`max_supply` were already present and are unchanged). Additive; no signatures changed.

---

## [0.5.0] - 2026-07-15

### Added

- Rate limiter: bounded waits (`CREWAI_TOOLS_RATE_LIMIT_MAX_WAIT`, default 120s) surfacing as `err()` envelopes via `RateLimitExceeded`; WARNING log for waits >5s; new provider limits for `TickerValidation`, `CoinGecko`, `DeFiLlama`.
- `crewai_custom_tools.tools.finance` subpackage now re-exports the full finance tool set (previously top-level only).

### Fixed

- SEC tool's rate-limit provider key (`SEC-EDGAR` → `SECEdgar`) — SEC calls were unthrottled.
- `YahooFinanceCompanyInfoTool` falls back to `info["revenueGrowth"]` on ANY financials-fetch failure (network errors previously errored the whole call).

---

## [0.4.0] - 2026-07-14

### Breaking

- `PerplexitySearchTool`: `focus`/`recency` params replaced by `model`/`top_k`/`search_recency`/`search_domain_filter`; construction now raises `ValueError` without `PERPLEXITY_API_KEY` (or legacy `PPLX_API_KEY`). The recency filter is now actually sent (`search_recency_filter`).
- `crewai` floor raised to `>=1.15.1`.
- MCP server: without a Perplexity key, `perplexity_search` is no longer listed by the MCP server (previously listed and errored per-call); the server itself still starts and serves all other tools.

### Added

- `parse_tool_result()` / `ToolResultError`: canonical envelope parsing for programmatic consumers.
- `require_api_key()`: fail-fast key validation with multi-var fallback.
- Provider-keyed synchronous rate limiter, enforced by `@api_tool` (disable with `CREWAI_TOOLS_RATE_LIMIT_DISABLED=1`).
- `perplexity_structured()` async function (JSON-schema structured research, ported from finwiz).
- `prefetched_data` batch mode on `YahooFinanceTickerInfoTool` and `YahooFinanceHistoryTool`.
- Yahoo ticker/history results now carry `timestamp` / `market_time` / `data_time` / `data_source`; ticker info gains finwiz's extended fundamental fields.
- `YahooFinanceCompanyInfoTool`: revenue growth calculated from actual financials; `debt_to_equity` converted to a ratio.

---

## [0.3.1] - 2026-07-09

### Fixed

- **`UnifiedRssTool` timezone-consistent date filtering** (#3): the day-granular cutoff was
  built from `datetime.now()` (naive local time) but compared against feed entry dates that
  feedparser normalises to UTC, skewing the boundary by the host's UTC offset on non-UTC
  servers. The cutoff is now naive-UTC, and `_entry_pub_date` converts tz-aware string dates
  to UTC before dropping tzinfo, so every date is directly comparable.
- **`UnifiedRssTool` bounded feed fetch** (#4): `feedparser.parse` had no network timeout, so
  a slow or hanging feed could stall the whole aggregation run. Each fetch now runs under a
  default socket timeout (`FEED_FETCH_TIMEOUT_S`, 20s), restored afterwards; a timing-out feed
  is caught and recorded as an invalid source instead of blocking.

---

## [0.3.0] - 2026-07-08

### Fixed

- **`SaveToRagTool` collection injection**: the tool now accepts an optional pre-configured
  `rag_tool` via its constructor (`SaveToRagTool(rag_tool=...)`) and stores into it, instead of
  always instantiating a bare default `RagTool()` — which wrote to the wrong chromadb
  collection/embeddings and silently broke save->retrieve. Falls back to a default `RagTool()`
  only when none is injected. Keeps the `save_to_rag` name, args schema, and
  `{success,data,error}` envelope.
- **`UnifiedRssTool` full-pipeline restoration**: restored the
  `_run(opml_file_path, days=7, output_file_path=None, invalid_sources_file_path=None)`
  signature, `RssFeeds` JSON **output-file writing**, article **content-scraping** (via the
  in-package resilient `UnifiedScraperTool`, with an optional Newspaper3k fast path), and
  **invalid-source tracking**. This makes the tool a drop-in for programmatic callers that
  invoke `._run(opml, days, output_file_path)` positionally and rely on the written file as the
  output.

### Added

- `tools/web/rss_models.py`: `Article` / `FeedWithArticles` / `RssFeeds` pydantic models
  describing the aggregated RSS JSON output contract.
- Dependency: `python-dateutil` (pure-Python) for RSS entry date fallback parsing.

## [0.2.0] - 2026-07-08

### Added

- **`ToolResult` envelope (`core/results.py`)**: every tool now returns a uniform
  `{"success": bool, "data": <any>|null, "error": <str>|null}` JSON string via the
  `ok()` / `err()` helpers, so callers can always distinguish a genuine failure from an
  empty-but-successful result.
- **47 newly centralized / rebuilt tools** (library now exports 87 tool classes). New
  capabilities: additional search providers (Brave, Tavily, SerpApi, Hybrid) and standalone
  scrapers; CoinMarketCap list/news/historical; enhanced ETF/crypto/DeFi analysis; TwelveData
  indicators; Alpha Vantage news-sentiment; ChartImg; structured Perplexity; INSEE Sirene,
  BODACC, GDELT, Google News RSS, Hunter finder/verifier; CLI-backed recon (sherlock,
  maigret, theHarvester, net_recon) with graceful gating; data-centric + report-writer
  tools; Geoapify, TechStack, Wikipedia processing, RSS aggregators, delegating email; and
  6 clean-rebuilt analytics tools (market screener, standardized risk scoring, SEC EDGAR
  analysis, VADER sentiment + cross-asset comparator, template-free HTML generator).
- **`core/cli_runner.py`**: hardened no-shell subprocess runner (target validation,
  PATH resolution, mandatory timeout, stdout cap) backing the CLI-based OSINT tools.
- **Full MCP parity**: `mcp_server.py` auto-registers every exported tool (81) instead of
  a hand-written subset.

### Fixed

- **~50 correctness/security findings** across the ported tools, including: Yahoo ETF
  holdings (called non-existent yfinance methods → always empty; now `get_funds_data()`),
  Yahoo news deprecated keys, history %-change divide-by-zero, Perplexity dead `focus`
  param + unguarded parse, username detection (HTTP-200-only → found/unknown/absent
  heuristic), RDAP `.co.uk` handling, both report renderers (one errored, one blanked),
  RAG false-success, AccuWeather cleartext key, Airtable URL encoding, and many non-JSON
  returns. Reporting **templates are now packaged** so they work on a `pip install`.

### Security

- Stored-XSS in HTML report rendering closed (escape untrusted section content).
- XXE hardening for OPML parsing via `defusedxml`.
- AccuWeather calls moved to HTTPS.

### Changed

- `@api_tool` returns a JSON error envelope on failure (was empty `{}`/`[]`).
- Added dependencies: `defusedxml`, `tldextract` (both pure-Python).

## [0.1.0] - 2026-07-05

### Added

- **Unified Caching Layer (`config/cache.py`)**:
  - Structured, thread-safe, self-healing file and memory cache using `.crewai_cache/`.
  - Added `@cache_api_call` decorator to easily apply caching to core sync functions.
  - Implemented SHA-256 and MD5 cryptographic hashing to ensure completely deterministic key generation across restarts (avoiding built-in randomized `hash()`).
  - Added dynamic class instance `self` inspection to strip memory addresses (like `0x...`), preventing cache misses when instance methods are decorated.
  - Robust `FileNotFoundError` and `JSONDecodeError` safety to handle concurrent race conditions.
- **Unified Tool Set (`tools/`)**:
  - `PerplexitySearchTool` (in `tools/web/perplexity.py`) featuring standard requests timeouts, dual-return formats (`"json"` or `"markdown"`), and multi-environmental api-key validation.
  - `YahooFinanceNewsTool` (in `tools/finance/yfinance_news.py`) returning structured news data for financial instruments, wrapped with safety borders.
  - `YahooFinanceTickerInfoTool` (in `tools/finance/yfinance_ticker.py`) extracting a standardized, clean metric subset (P/E ratio, Market Cap, Beta) for assets, ETFs, and cryptos.
- **Top-Level Exports**: Exposes `PerplexitySearchTool`, `YahooFinanceTickerInfoTool`, and `YahooFinanceNewsTool` directly from `crewai_custom_tools`.
- **Comprehensive Pytest Suite**: 40 unit and integration tests covering versions, caching layers, filename collision, metadata preservation, wraps decorator, error responses, and mock APIs.

### Changed

- **Modular Packaging**: Renamed library package from `crewai-tools` to `crewai-custom-tools` to prevent PyPI conflicts, updating all workspace files and plan structures.
- **Extracted Optional Extras**: Isolated `yfinance` under `[finance]` extra and `pytest-mock` under `[dev]` extra inside `pyproject.toml` to minimize base deployment size.
- **Standard Logging**: Swapped all custom logger formats (Loguru bracket syntax `{}`) to standard Python `logging` for lightweight compatibility.
- **Failure Non-Caching Policy**: Refactored financial news fetching to ensure exception payloads and rate limits are never cached permanently, allowing immediate recovery on subsequent execution.
