# Changelog

All notable changes to the `crewai-custom-tools` project will be documented in this file.

---

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
