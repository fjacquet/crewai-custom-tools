# crew-custom-tools

> **Centralized, resilient, and high-performance tools for CrewAI multi-agent systems.**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/fjacquet/crewai_custom_tools/blob/main/LICENSE)
[![Latest Release](https://img.shields.io/github/v/release/fjacquet/crewai_custom_tools?color=orange)](https://github.com/fjacquet/crewai_custom_tools/releases/tag/v0.1.0)
[![CI Pipeline](https://github.com/fjacquet/crewai_custom_tools/actions/workflows/ci.yml/badge.svg)](https://github.com/fjacquet/crewai_custom_tools/actions)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://fjacquet.github.io/crew_custom_tools)

---

## 📖 Welcome

`crew-custom-tools` unifies and centralizes overlapping, duplicated, and specialized multi-agent toolkits from five distinct source codebases into a single, cohesive **Universal Monolith (Approach A)** package. 

- **Source Code Repository**: [GitHub - fjacquet/crewai_custom_tools](https://github.com/fjacquet/crewai_custom_tools)
- **Current Version**: [v0.1.0 (Initial Consolidated Release)](https://github.com/fjacquet/crewai_custom_tools/releases/tag/v0.1.0)
- **Interactive Documentation**: [GitHub Pages User Guide](https://fjacquet.github.io/crew_custom_tools)

---

## 🛠️ Superpower Domains Excluded

The library packs over 30+ standardized, Pydantic-validated tools across five major categories:

1.  **Web Search & Scraping**: Perplexity AI queries, Serper.dev, auto-escalating crawlers (BeautifulSoup -> ScrapeNinja -> Firecrawl), Wikipedia REST interfaces, and RSS parsers.
2.  **Quantitative Stocks & Markets**: Yahoo Finance metrics, ETF holdings, CoinMarketCap quotes, Kraken balances, FRED macroeconomic observations, CNN Fear/Greed sentiment indexes, and exchange rates.
3.  **OSINT Cyber Recon**: Multi-platform username scanner, crt.sh subdomains, whodap RDAP registrar lookup, and French public registries (recherche-entreprises API).
4.  **Rich Document Compilation**: Standardized HTML layout renderers (PESTEL, Financial) and WeasyPrint PDF compile-dossiers.
5.  **Workspace Enterprise**: Todoist tasks, Airtable databases, AccuWeather climates, and Vector DB RAG database storages.

---

## ⚡ Quickstart

```bash
# Install editable local package with development dependencies
uv add --editable /Users/fjacquet/Projects/crew_custom_tools

# Run our local FastMCP stdio server
uv run crew-custom-tools-mcp
```

Import and invoke tools directly from your python scripts with zero boilerplate:
```python
from crew_custom_tools import PerplexitySearchTool, UnifiedScraperTool, FrenchRegistryTool

# Initialize and query keyless French registries
registry = FrenchRegistryTool()
print(registry._run(query="LVMH"))
```

---

## ⚡ Robust Core Infrastructure

- **Secure SHA-256 TTL Caching**: Thread-safe persistent memory and disk caching with automatic corruption recovery (completely bypassing weak MD5 keying).
- **Decorated API Resiliency**: `@api_tool` wrappers providing automatic retries on HTTP 429 rate limits, and non-blocking `ThreadPoolExecutor` execution timeouts to prevent hanging multi-agent loops.
- **100% Mock Test Coverage**: 87 highly stable, offline unit and integration tests executing in under 5.0 seconds (4.90s!).
