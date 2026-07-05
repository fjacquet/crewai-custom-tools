# Design Specification: crew-custom-tools (Universal Monolith Edition)

**Date**: 2026-07-05  
**Status**: APPROVED / READY FOR IMPLEMENTATION PLAN  
**Author**: Gemini CLI & Collaborative Engineering Team  

---

## 1. Executive Summary

This document specifies the design for a consolidated, highly robust, and complete CrewAI tools library (`crew-custom-tools`). Built as an **exclusive Universal Monolith (Approach A)**, this library unifies overlapping, duplicated, and specialized tools from five distinct agentic codebases:

1. `/Users/fjacquet/Projects/osint_tools`
2. `/Users/fjacquet/Projects/finwiz`
3. `/Users/fjacquet/Projects/crews/epic_news`
4. `/Users/fjacquet/Projects/crews/osint_home`
5. `/Users/fjacquet/Projects/crews/menu_planner`

By combining these files, we eliminate technical debt, standardise on a modern thread-safe cache system, inject uniform API resiliency, and provide a single packaging namespace.

---

## 2. Packaging and Dependencies (`pyproject.toml`)

Under the **Universal Monolith** design, all dependencies are fully integrated into the core package. To avoid building complex binary C extensions (like `ta-lib` or `quantlib`), standard quantitative calculations are implemented using pure, vectorized `numpy` and `pandas` code, or via direct REST API client calls.

### 2.1 Complete `pyproject.toml` Specifications

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "crew-custom-tools"
version = "0.1.0"
description = "Centralized, resilient tools for CrewAI multi-agent systems"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    # Core multi-agent runtime
    "crewai>=0.100.0",
    "pydantic>=2.0.0",
    "requests>=2.31.0",
    "httpx>=0.28.1",
    "beautifulsoup4>=4.12.0",
    "jinja2>=3.1.6",
    
    # Financial & quantitative libraries
    "yfinance>=0.2.38",
    "numpy>=1.24.0",
    "pandas>=2.0.0",
    
    # OSINT & domain tools
    "pygithub>=2.2.0",
    "whodap>=0.1.16",
    "feedparser>=6.0.12",
    
    # Enterprise APIs
    "todoist-api-python>=2.1.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.15.1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/crew_custom_tools"]
```

---

## 3. Directory Layout

The workspace files are organized neatly by category:

```text
src/crew_custom_tools/
├── __init__.py                    # Public exports for all tools
├── config/
│   ├── __init__.py
│   └── cache.py                   # Standard thread-safe filesystem & in-memory TTL caching
├── core/
│   ├── __init__.py
│   └── decorators.py              # Advanced resiliency, timeout, retry, and caching decorators
├── models/                        # Centralized Pydantic models (migrated from source projects)
│   ├── __init__.py
│   ├── web_search_models.py       # Tavily, Perplexity models
│   ├── finance_models.py          # Stocks, Tickers, Crypto, FRED models
│   ├── github_models.py           # GitHub repositories & org schemas
│   ├── email_models.py            # Hunter.io & validation layouts
│   ├── rss_models.py              # RSS entries & OPML feed structures
│   ├── airtable_models.py         # Airtable configuration schemas
│   ├── todoist_models.py          # Todoist tasks schemas
│   └── reports/                   # Document/Dossier structures
│       ├── __init__.py
│       ├── pestel.py
│       ├── prospecting.py
│       ├── contact.py
│       └── dossier.py
└── tools/
    ├── __init__.py
    ├── web/                       # WEB SEARCH & SCRAPING
    │   ├── __init__.py
    │   ├── perplexity.py          # Dual-format Perplexity search
    │   ├── serper.py              # Google Serper & SafeSerper search
    │   ├── scraper.py             # ScraperFactory & ScrapeNinja integration
    │   ├── wikipedia.py           # Wikipedia search & article extraction
    │   ├── rss.py                 # Unified RSS & OPML feed reader/parser
    │   └── fact_checking.py       # Google Fact Check utilities
    ├── finance/                   # STOCKS, CRYPTO & QUANTITATIVE
    │   ├── __init__.py
    │   ├── yfinance_ticker.py     # Stocks/ETFs core metrics with caching
    │   ├── yfinance_news.py       # Yahoo Finance news headlines
    │   ├── company_info.py        # Company description, profile & officer stats
    │   ├── history_holdings.py    # Historical price fetching & ETF holdings
    │   ├── crypto.py              # CoinMarketCap (news/history) & Kraken API
    │   ├── market_data.py         # Alpha Vantage, Tiingo & FRED economic data
    │   ├── fear_greed.py          # Fear & Greed index scraper
    │   └── exchange_rate.py       # Fiat currency exchange rates
    ├── osint/                     # OSINT & BUSINESS INTELLIGENCE
    │   ├── __init__.py
    │   ├── github.py              # GitHub repos, org, & user search
    │   ├── email_recon.py         # Hunter.io & email validation
    │   ├── person_recon.py        # Username checking (Sherlock, Maigret checks)
    │   ├── domain_recon.py        # crt.sh certificate transparency & whodap RDAP lookups
    │   └── registers.py           # French corporate registries (Sirene, Bodacc, recherche-entreprises)
    ├── reporting/                 # REPORT GENERATION & BEAUTIFICATION
    │   ├── __init__.py
    │   ├── pdf_generator.py       # HTML-to-PDF layout rendering & formatting
    │   ├── html_generator.py      # Rich dashboard generator & Markdown-to-HTML beautifier
    │   └── template_renderers.py  # Specialized renderers (Pestel, Financial, HR, Geospatial)
    └── enterprise/                # WORKSPACE INTEGRATIONS & KNOWLEDGE BASES
        ├── __init__.py
        ├── todoist.py             # Todoist project/task sync
        ├── airtable.py            # Airtable reading/writing
        ├── accuweather.py         # Weather checks & conditions
        └── rag_tools.py           # Save-to-RAG and Query-RAG adapters
```

---

## 4. Core Resiliency & Caching Architecture

### 4.1 Caching Layer (`config/cache.py`)

*   **Design**: Features dual-level in-memory and filesystem storage with automatic time-to-live (TTL) expiration rules.
*   **Safety**: If a cache file is corrupted or contains incomplete text, it catches `json.JSONDecodeError` or `OSError` dynamically, purges the broken cache file from the disk, logs the warning, and safely behaves as a cache miss instead of crashing.
*   **Key Security**: Utilizes strong cryptographic hashes (`hashlib.sha256`) instead of weak/broken MD5 algorithms to map dynamic parameters and queries into standardized, 40-character collision-resistant file names.
*   **Decorators**: Implements `@cache_api_call` to automatically handle parameter serialization, metadata wrapping (`functools.wraps`), and persistence across execution sessions.

### 4.2 API Resiliency Decorators (`core/decorators.py`)

*   **Retry Protocols**: Automatically intercepts HTTP rate limits (`429`) and server errors (`5xx`). Executes retry attempts with exponential backoff and randomized jitter to prevent thundering herds.
*   **Timeout Boundaries**: Enforces strict execution limits on all network requests (default: 30.0s) to keep multi-agent loops moving.
*   **Unhandled Exceptions Handling**: Wraps execution in safe boundaries. Catches all connection failures, socket errors, or API-specific failures. Instead of raising an exception and crashing the entire agent team, it returns a clean, agent-readable error description so the agent can react, adapt, or output a graceful fallback result.

---

## 5. Pydantic Objects Standard

Every tool in the unified suite strictly declares its input parameters using Pydantic schemas (inheriting from `pydantic.BaseModel`). 
*   **Agent Integration**: The Pydantic model's attribute types, descriptions, and default values are dynamically parsed by the downstream LLM agent to construct valid argument inputs.
*   **Output Standardization**: Multi-step or data-centric tools validate their JSON outputs against migrated models (like `TavilySearchResult`, `GithubRepoDetails`, `YahooFinanceTickerDetails`), guaranteeing structural consistency.

---

## 6. Testing & Validation Strategy

*   **Porting Existing Assets**: We will port, clean up, and adapt the extensive test suites already written in `epic_news`, `finwiz`, and `osint_tools`. This avoids reinventing tests and saves operational development time.
*   **Strict pytest Standard**: All tests must follow the modern **pytest** standard utilizing fixtures, parameterization, and `pytest-mock`. **No `unittest` module styles will be used or written.**
*   **Zero Live Connections**: All ported and new tests must execute 100% offline via mock responses (`pytest-mock`), simulating successes, timeouts, and `429` rate limit returns to verify resilience.
*   **Performance Constraint**: The complete test suite of 40+ unit and integration tests must run and pass in under 5 seconds.

---

## 7. Spec Self-Review Checklist

1.  **Placeholder Scan**: No "TBD", "TODO", or incomplete statements. All imports and directories are fully specified.
2.  **Internal Consistency**: All modules and files listed in the target layout align with the dependencies and Pydantic object migration strategies.
3.  **Scope Verification**: Focuses purely on extracting, consolidating, and sanitizing existing functional codebase assets rather than writing new business logic from scratch.
