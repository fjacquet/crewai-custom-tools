# crewai-custom-tools

> **Centralized, resilient, and high-performance tools for CrewAI multi-agent systems.**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/fjacquet/crewai-custom-tools/blob/main/LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/fjacquet/crewai-custom-tools?color=orange)](https://github.com/fjacquet/crewai-custom-tools/releases/tag/v0.1.0)
[![CI Pipeline](https://github.com/fjacquet/crewai-custom-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/crewai-custom-tools/actions)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://fjacquet.github.io/crewai-custom-tools)

---

## 📖 Welcome

`crewai-custom-tools` unifies and centralizes overlapping, duplicated, and specialized multi-agent toolkits from five distinct source codebases into a single, cohesive **Universal Monolith (Approach A)** package.

- **Source Code Repository**: [GitHub - fjacquet/crewai-custom-tools](https://github.com/fjacquet/crewai-custom-tools)
- **Current Version**: [v0.1.0 (Initial Consolidated Release)](https://github.com/fjacquet/crewai-custom-tools/releases/tag/v0.1.0)
- **Interactive Documentation**: [GitHub Pages User Guide](https://fjacquet.github.io/crewai-custom-tools)

---

## 🛠️ Superpower Domains Excluded

The library packs over 30+ standardized, Pydantic-validated tools across five major categories:

1. **Web Search & Scraping**: Perplexity AI queries, Serper.dev, auto-escalating crawlers (BeautifulSoup -> ScrapeNinja -> Firecrawl), Wikipedia REST interfaces, and RSS parsers.
2. **Quantitative Stocks & Markets**: Yahoo Finance metrics, ETF holdings, CoinMarketCap quotes, Kraken balances, FRED macroeconomic observations, CNN Fear/Greed sentiment indexes, and exchange rates.
3. **OSINT Cyber Recon**: Multi-platform username scanner, crt.sh subdomains, whodap RDAP registrar lookup, and French public registries (recherche-entreprises API).
4. **Rich Document Compilation**: Standardized HTML layout renderers (PESTEL, Financial) and WeasyPrint PDF compile-dossiers.
5. **Workspace Enterprise**: Todoist tasks, Airtable databases, AccuWeather climates, and Vector DB RAG database storages.

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

---

## ⚡ Quickstart

```bash
# Install editable local package with development dependencies
uv add --editable /Users/fjacquet/Projects/crewai_custom_tools

# Run our local FastMCP stdio server
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

- **Secure SHA-256 TTL Caching**: Thread-safe persistent memory and disk caching with automatic corruption recovery (completely bypassing weak MD5 keying).
- **Decorated API Resiliency**: `@api_tool` wrappers providing automatic retries on HTTP 429 rate limits, and non-blocking `ThreadPoolExecutor` execution timeouts to prevent hanging multi-agent loops.
- **100% Mock Test Coverage**: 87 highly stable, offline unit and integration tests executing in under 5.0 seconds (4.90s!).
