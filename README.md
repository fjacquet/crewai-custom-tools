# crewai-custom-tools

> **Centralized, resilient, and high-performance tools for CrewAI multi-agent systems.**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/fjacquet/crewai-custom-tools/blob/main/LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/fjacquet/crewai-custom-tools?color=orange)](https://github.com/fjacquet/crewai-custom-tools/releases)
[![CI Pipeline](https://github.com/fjacquet/crewai-custom-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/crewai-custom-tools/actions)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://fjacquet.github.io/crewai-custom-tools)

---

## 📖 Welcome

`crewai-custom-tools` unifies and centralizes overlapping, duplicated, and specialized multi-agent toolkits from three source codebases — `finwiz`, `osint_tools` and `epic_news` — into a single, cohesive **Universal Monolith (Approach A)** package.

- **Source Code Repository**: [GitHub - fjacquet/crewai-custom-tools](https://github.com/fjacquet/crewai-custom-tools)
- **Changelog**: [CHANGELOG.md](https://github.com/fjacquet/crewai-custom-tools/blob/main/CHANGELOG.md) — the current version is the one in the release badge above.
- **Interactive Documentation**: [GitHub Pages User Guide](https://fjacquet.github.io/crewai-custom-tools)

---

## 🛠️ Superpower Domains Included

Every tool is a Pydantic-validated `BaseTool` returning the same `ToolResult` envelope, across seven domains:

1. **Web Search & Scraping**: Perplexity AI queries, Serper.dev, auto-escalating crawlers (BeautifulSoup -> ScrapeNinja -> Firecrawl), Wikipedia REST interfaces, and RSS parsers.
2. **Quantitative Stocks & Markets**: Yahoo Finance metrics, ETF holdings, CoinMarketCap quotes, Kraken balances, FRED macroeconomic observations, CNN Fear/Greed sentiment indexes, exchange rates, and pure-function analytics (valuation, ETF analysis, regulatory compliance, position sizing, price targets, A+ scoring/screening).
3. **OSINT Cyber Recon**: Multi-platform username scanner, crt.sh subdomains, whodap RDAP registrar lookup, and French public registries (recherche-entreprises API).
4. **Genealogy**: Gramps API read and write tools, consistency rules, duplicate detection, name standardization, gender inference, and archive-source leads (matchID, Wikidata, DHS). Consumed by the sibling `genecrew` project.
5. **Rich Document Compilation**: Standardized HTML layout renderers (PESTEL, Financial) and WeasyPrint PDF compile-dossiers.
6. **Workspace Enterprise**: Todoist tasks, Airtable databases, AccuWeather climates, and Vector DB RAG database storages.
7. **Files**: `FileReadTool` / `DirectoryReadTool` for local file and directory reads.

---

## 🔑 API Key Reference Registry

To activate and configure our external API integrations, set the following environment variables. Many OSINT and web tools support a **Hybrid Auth** mode, offering immediate keyless fallbacks out of the box and upgrading automatically when key parameters are set.

| Environment Variable | Target Tool | Status | Provider & Description |
|---|---|---|---|
| `PERPLEXITY_API_KEY` | `PerplexitySearchTool` | **STRICTLY REQUIRED** | Perplexity AI. Search & synthesize academic/web news. |
| `SERPER_API_KEY` | `SerperSearchTool` | **STRICTLY REQUIRED** | Google Serper. Organic Google search. |
| `GITHUB_TOKEN` | `GitHubSearchTool` | **STRICTLY REQUIRED** | GitHub API. Read public repos, orgs, and issue lists. |
| `TODOIST_API_KEY` | `TodoistTool` | **STRICTLY REQUIRED** | Todoist. Synchronize tasks and project boards. |
| `AIRTABLE_API_KEY` | `AirtableTool` | **STRICTLY REQUIRED** | Airtable. Read/write database records. |
| `ACCUWEATHER_API_KEY` | `AccuWeatherTool` | **STRICTLY REQUIRED** | AccuWeather. Fetch city meteorological conditions. |
| `COINMARKETCAP_API_KEY` | `CoinMarketCapInfoTool` | **STRICTLY REQUIRED** | CoinMarketCap. Real-time cryptocurrency quotes. |
| `KRAKEN_API_KEY` / `_SECRET` | `KrakenAssetListTool` | **STRICTLY REQUIRED** | Kraken. Verify account balance quantities. |
| `RAPIDAPI_KEY` | `UnifiedScraperTool` | *OPTIONAL (FALLBACK)* | ScrapeNinja. Bypasses Cloudflare & JS rendering blockages. |
| `FIRECRAWL_API_KEY` | `UnifiedScraperTool` | *OPTIONAL (FALLBACK)* | Firecrawl. Dynamic scraping & markdown extraction. |
| `EPIEOS_API_KEY` | `EpieosEmailLookupTool` | *OPTIONAL (FALLBACK)* | Epieos. Reverse email social-profile lookups. |
| `OPENCORPORATES_API_KEY` | `OpenCorporatesSearchTool`| *OPTIONAL (FALLBACK)* | OpenCorporates. High-speed global corporate registry. |
| `FRED_API_KEY` | `FREDMacroTool` | *OPTIONAL (FALLBACK)* | St. Louis Fed. Key macroeconomic indicators. |
| `ALPHA_VANTAGE_API_KEY` | `AlphaVantageOverviewTool`| *OPTIONAL (FALLBACK)* | Alpha Vantage. Company balance-sheet overview metrics. |
| `BRAVE_API_KEY` | `BraveSearchTool` | *OPTIONAL* | Brave Search API. |
| `TAVILY_API_KEY` | `TavilyTool` | *OPTIONAL* | Tavily AI search. |
| `SERPAPI_API_KEY` | `SerpApiTool` | *OPTIONAL* | SerpApi (serpapi.com) organic search. |
| `TWELVE_DATA_API_KEY` | `TwelveDataIndicatorTool` | *OPTIONAL* | Twelve Data. Technical indicators (RSI/MACD/…). |
| `CHART_IMG_API_KEY` | `ChartImgTool` | *OPTIONAL* | chart-img.com. Rendered chart images. |
| `GEOAPIFY_API_KEY` | `GeoapifyPlacesTool` | *OPTIONAL* | Geoapify. Places / POI lookup. |
| `HUNTER_API_KEY` | `HunterIOTool`, `HunterEmailFinderTool` | *OPTIONAL* | Hunter.io. Email discovery / verification. |
| `INSEE_SIRENE_API_KEY` | `InseeSireneTool` | *OPTIONAL* | INSEE Sirene. Authoritative FR firmographics. |
| `GOOGLE_API_KEY` | `GoogleFactCheckTool` | *OPTIONAL* | Google Fact Check Tools API. |

> The CLI-backed OSINT tools (`SherlockTool`, `MaigretTool`, `TheHarvesterTool`, `NetReconTool`) need their respective binaries on `PATH`; they return a clear error when the binary is absent, so the package installs and runs everywhere.

---

## ⚡ Quickstart

```bash
# Add it to your project, straight from GitHub
uv add "git+https://github.com/fjacquet/crewai-custom-tools"

# Or, to hack on the library itself: clone, then install it editable
git clone https://github.com/fjacquet/crewai-custom-tools
cd crewai-custom-tools
uv pip install -e ".[dev]"

# Run the local FastMCP stdio server
uv run crewai-custom-tools-mcp
```

Import and invoke tools directly from your python scripts with zero boilerplate:

```python
from crewai_custom_tools import PerplexitySearchTool, UnifiedScraperTool, FrenchRegistryTool

# Initialize and query keyless French registries
registry = FrenchRegistryTool()
print(registry._run(query="LVMH"))
```

---

## ⚡ Robust Core Infrastructure

- **Uniform `ToolResult` envelope**: every tool returns `{"success", "data", "error"}` as a JSON string, so an agent can always distinguish a genuine failure from an empty-but-successful result.
- **Decorated API Resiliency**: the `@api_tool` wrapper adds per-call timeouts (via a `ThreadPoolExecutor`, to prevent hanging multi-agent loops), one automatic retry on HTTP 429, and converts any failure into a JSON error envelope.
- **SHA-256 TTL caching**: thread-safe memory and disk cache with automatic corruption recovery, used by the Yahoo Finance tools.
- **Fully offline test suite**: every test is mocked, so the whole suite runs in seconds with no network and no API key.
- **Full MCP parity**: the FastMCP stdio server auto-registers every tool exported from `__all__`, deriving each MCP signature from the tool's `args_schema` — a new library export appears in MCP with no per-tool wrapper (`uv run crewai-custom-tools-mcp`).
