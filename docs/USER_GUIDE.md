# `crewai-custom-tools` User Guide (Universal Monolith Edition)

Welcome to the **`crewai-custom-tools`** library! This guide outlines how to install the package, import and configure our consolidated, premium superpower tools, utilize the persistent caching layer and resiliency decorators, and write custom multi-agent scripts out of the box.

* **Source Code Repository**: [GitHub - fjacquet/crewai-custom-tools](https://github.com/fjacquet/crewai-custom-tools)
* **Latest Release**: [v0.1.0 (Initial Consolidated Release)](https://github.com/fjacquet/crewai-custom-tools/releases/tag/v0.1.0)
* **Documentation Site**: [GitHub Pages User Guide](https://fjacquet.github.io/crewai-custom-tools)

---

## 1. Installation & Environment Setup

`crewai-custom-tools` is packaged as an **exclusive Universal Monolith (Approach A)**. All third-party libraries and requirements are fully integrated and available out of the box with zero external dependency fragmentation.

### 1.1 Local Development (Editable Mode)

To use `crewai-custom-tools` in your other multi-agent projects (such as `epic_news`, `finwiz`, or `osint_tools`) in editable mode:

```bash
# Navigate to your agent project (e.g., epic_news)
uv add --editable /Users/fjacquet/Projects/crewai_custom_tools
```

### 1.2 Development and C-Library Fallbacks

Our financial and macroeconomic scoring systems contain robust **pure-Python fallback calculations** using standard `numpy` and `pandas` arrays. This guarantees that you can install and execute all tools on macOS, Linux, or Windows without being blocked by compiling complex system C libraries (like `ta-lib` or `quantlib`).

### 1.3 API Key Reference Registry

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

## 2. Namespace & Exposing the Tools

To maximize convenience for multi-agent LLM systems, **all 30+ custom tools and decorators are exposed directly from the package-level root namespace**:

```python
# Import anything cleanly from the root namespace!
from crewai_custom_tools import (
    # Web & Search
    PerplexitySearchTool,
    SerperSearchTool,
    UnifiedScraperTool,
    WikipediaSearchTool,
    WikipediaArticleTool,
    RssFeedParserTool,
    OpmlParserTool,
    GoogleFactCheckTool,

    # Stocks & Financial
    YahooFinanceTickerInfoTool,
    YahooFinanceNewsTool,
    YahooFinanceCompanyInfoTool,
    YahooFinanceETFHoldingsTool,
    YahooFinanceHistoryTool,
    CoinMarketCapInfoTool,
    KrakenTickerInfoTool,
    KrakenAssetListTool,
    FREDMacroTool,
    AlphaVantageOverviewTool,
    FearGreedTool,
    ExchangeRateTool,

    # OSINT & Cyber Recon
    GitHubSearchTool,
    GitHubOrgSearchTool,
    HunterIOTool,
    SerperEmailSearchTool,
    UsernameSearchTool,
    CrtShTool,
    RDAPDomainTool,
    FrenchRegistryTool,

    # Reporting & Formatting
    RenderReportTool,
    PestelReportRenderer,
    FinancialReportRenderer,
    HtmlToPdfTool,
    validate_html,

    # Workspace & Enterprise
    TodoistTool,
    AirtableReaderTool,
    AirtableTool,
    AccuWeatherTool,
    SaveToRagTool
)
```

---

## 3. Tool Usage Examples

### 3.1 Web Search: `UnifiedScraperTool` (Resilient Crawler with fallbacks)

This tool scrapes raw HTML/text from any URL. It defaults to a fast standard BeautifulSoup scraper, but **automatically escalates and routes requests through ScrapeNinja or Firecrawl proxy APIs** if Cloudflare or Javascript rendering blocks the request.

```python
import os
from crewai_custom_tools import UnifiedScraperTool

# Optionally set keys in your environment for automatic proxy escalations
os.environ["RAPIDAPI_KEY"] = "your_scrapeninja_rapidapi_key"
os.environ["FIRECRAWL_API_KEY"] = "your_firecrawl_api_key"

tool = UnifiedScraperTool()

# 1. Standard BeautifulSoup scraper runs (fast, zero key required)
result_json = tool._run(url="https://news.ycombinator.com")

# 2. Force ScrapeNinja proxy scraper
scrapeninja_result = tool._run(url="https://js-rendered-protected-site.com", provider="scrapeninja")
```

### 3.2 Finance: `YahooFinanceETFHoldingsTool` & `FREDMacroTool`

Retrieve ETF breakdowns and Federal Reserve macroeconomic data (FED funds rate, unemployment, CPI inflation) cleanly.

```python
import os
from crewai_custom_tools import YahooFinanceETFHoldingsTool, FREDMacroTool

# 1. Fetch Vanguard S&P 500 ETF (VOO) holdings
etf_tool = YahooFinanceETFHoldingsTool()
holdings_json = etf_tool._run(ticker="VOO")
print(holdings_json)

# 2. Fetch latest FED Interest Rate directly from FRED API
os.environ["FRED_API_KEY"] = "your_fred_api_key"
fred_tool = FREDMacroTool()
fed_rate_json = fred_tool._run(indicator="fed_rate")
print(fed_rate_json)
```

### 3.3 OSINT: `FrenchRegistryTool` & `UsernameSearchTool`

Discover corporate registration metadata from keyless official registries or scan for user social-media presence.

```python
from crewai_custom_tools import FrenchRegistryTool, UsernameSearchTool

# 1. Search the official keyless French corporate register (recherche-entreprises)
registry_tool = FrenchRegistryTool()
company_metadata = registry_tool._run(query="LVMH") # Accept SIREN or Company Name
print(company_metadata)

# 2. Run high-speed, parallel-friendly social account profile checks (Sherlock-style)
username_tool = UsernameSearchTool()
hits_json = username_tool._run(username="fjacquet")
print(hits_json)
```

### 3.4 Reporting: `RenderReportTool` & `HtmlToPdfTool`

Renders standardized beautiful HTML templates (Pestel, Data, Financial) using Jinja2 and compiles them into professional PDF dossiers via WeasyPrint.

```python
from crewai_custom_tools import RenderReportTool, HtmlToPdfTool

# 1. Render a professional report using template_name
renderer = RenderReportTool()
rendered_html = renderer._run(
    title="Corporate Dossier",
    sections=[{"heading": "Abstract", "content": "This is a brief summary."}],
    template_name="professional_report_template.html"
)

# Save the HTML to disk
with open("dossier.html", "w") as f:
    f.write(rendered_html)

# 2. Compile HTML into a PDF file
pdf_compiler = HtmlToPdfTool()
pdf_compiler._run(html_file_path="dossier.html", output_pdf_path="dossier.pdf")
```

---

## 4. Utilizing the Caching and Resiliency Layers

Our custom thread-safe TTL caching system and `@api_tool` decorator form the core backbone of the library, keeping multi-agent crews highly stable.

### 4.1 Caching Layer (`config/cache.py`)

* **Persistent & Thread-Safe**: Features memory and disk persistence across python script executions.
* **Modern Hashing**: All cache filenames are mapped using cryptographic **SHA-256** digests truncated to 32 characters (completely avoiding weak MD5).
* **Self-Healing**: Automatically catches corruption, malformed text, or JSON write errors dynamically, purging corrupted cache files and failing safe instead of crashing.

### 4.2 Resiliency Decorator (`core/decorators.py`)

All network-bound tools in this package use the `@api_tool` decorator:

* **Automatic Rate Limit Retries**: Catches HTTP `429` statuses and automatically retries with polite sleep delays.
* **Non-Blocking Execution Timeouts**: Employs non-blocking `ThreadPoolExecutor` and `executor.shutdown(wait=False)` to guarantee strict execution timeouts, returning graceful error fallback strings to the calling agent if a remote API hangs.

---

## 5. Directory Mapping and Source Code Locations

The source files of `crewai-custom-tools` are structured cleanly under `src/crewai_custom_tools/`:

* `config/cache.py`: Thread-safe caching engine.
* `core/decorators.py`: `@api_tool` retry/timeout boundaries.
* `models/`: Centralized Pydantic schemas (e.g., `finance_models.py`, `github_models.py`, etc.).
* `tools/web/`: Perplexity, Serper, fallback scraper, Wikipedia API, RSS/OPML feeds.
* `tools/finance/`: Yahoo Finance (history, holdings, company info), CoinMarketCap, Kraken, Alpha Vantage, FRED, CNN Fear/Greed.
* `tools/osint/`: GitHub (search, orgs), email intelligence (Hunter, Serper), username checking, crt.sh subdomains, RDAP WHOIS, French corporate registers.
* `reporting/`: HTML validating, PDF compilation, specialized layout templates.
* `enterprise/`: Todoist, Airtable, AccuWeather, RAG vector DB adapters.
