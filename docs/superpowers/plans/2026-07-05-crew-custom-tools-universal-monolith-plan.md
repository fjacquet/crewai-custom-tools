# crewai-custom-tools Universal Monolith Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate and unify overlapping, duplicated, and specialized CrewAI tools from five codebases into a robust, high-performance, and resilient Universal Monolith local package.

**Architecture:** A single-dependency local package organized into logical domains (Web, Finance, OSINT, Reporting, Enterprise) powered by a centralized SHA-256 thread-safe TTL caching system, strict Pydantic model validation, and resilient error/rate-limit boundary decorators.

**Tech Stack:** Python 3.11+, `pytest>=8.0.0` (TDD / Mock-based tests), `crewai>=0.100.0`, `requests`, `pydantic>=2.0.0`, `beautifulsoup4`, `yfinance`, `pygithub`, `whodap`, `jinja2`.

## Global Constraints

- **Universal Monolith Pattern**: All requirements are added directly into core dependencies of `pyproject.toml`.
- **Pure Python Quant fallbacks**: Avoid installing heavy binary compile-dependent libraries (`ta-lib` / `quantlib`); implement any mathematical fallback logic using standard `numpy`/`pandas` arrays.
- **SHA-256 Keying**: Absolutely no MD5 is permitted for cache key hashes; standardize on `hashlib.sha256` digests truncated to 32 characters.
- **Clean Namespace Exports**: Expose all public tools and models inside the package root `__init__.py` for simple importing.
- **Strict pytest Rule**: All tests must use `pytest` with mock structures. Absolutely no `unittest` class patterns allowed.

---

### Task 1: Package Dependencies & Infrastructure Setup

**Files:**

- Modify: `pyproject.toml`
- Create: `src/crewai_custom_tools/models/__init__.py`
- Modify: `src/crewai_custom_tools/__init__.py`

**Interfaces:**

- Consumes: None
- Produces: Updated local package environment containing all essential libraries.

- [ ] **Step 1: Write complete pyproject.toml dependencies**

Update `pyproject.toml` core block:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "crewai-custom-tools"
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
packages = ["src/crewai_custom_tools"]
```

- [ ] **Step 2: Initialize Pydantic models root package directory**

Create file `src/crewai_custom_tools/models/__init__.py`:

```python
"""Centralized Pydantic models for crewai-custom-tools."""
```

- [ ] **Step 3: Verify uv installation**

Run command to perform a clean, editable install:

```bash
rtk proxy uv pip install -e ".[dev]"
```

Expected: Package installs with all monolith dependencies successfully.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/crewai_custom_tools/models/__init__.py
git commit -m "chore: setup universal monolith dependencies and models package"
```

---

### Task 2: Core Resiliency & SHA-256 Caching Layer

**Files:**

- Create/Overwrite: `src/crewai_custom_tools/config/cache.py`
- Create/Overwrite: `src/crewai_custom_tools/core/decorators.py`
- Create: `src/crewai_custom_tools/core/__init__.py`
- Test: `tests/test_cache.py`

**Interfaces:**

- Consumes: Standard Python `hashlib` and filesystem calls.
- Produces:
  - CacheManager: File and memory TTL cache.
  - `@cache_api_call`: Function caching decorator.
  - `@api_tool`: Resiliency retry and fallback wrapper.

- [ ] **Step 1: Write/Update the cache manager utilizing SHA-256**

Overwrite `src/crewai_custom_tools/config/cache.py` to enforce `hashlib.sha256` truncated key names:

```python
import os
import json
import time
import hashlib
from typing import Any, Optional
import logging

logger = logging.getLogger("crewai_custom_tools.cache")

class CacheManager:
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = cache_dir
        self.memory_cache = {}
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_filename(self, key: str) -> str:
        # Secure, modern SHA-256 hashing to map keys into safe file paths without MD5
        hasher = hashlib.sha256(key.encode('utf-8'))
        return os.path.join(self.cache_dir, f"cache_{hasher.hexdigest()[:32]}.json")

    def get(self, key: str) -> Optional[Any]:
        # Memory check first
        if key in self.memory_cache:
            val, expiry = self.memory_cache[key]
            if expiry is None or expiry > time.time():
                return val
            else:
                del self.memory_cache[key]

        filepath = self._get_filename(key)
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            val = data.get("value")
            expiry = data.get("expiry")
            if expiry is None or expiry > time.time():
                self.memory_cache[key] = (val, expiry)
                return val
            else:
                os.remove(filepath)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Purging corrupted cache file {filepath} due to error: {e}")
            try:
                os.remove(filepath)
            except OSError:
                pass
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = time.time() + ttl if ttl is not None else None
        self.memory_cache[key] = (value, expiry)
        filepath = self._get_filename(key)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({"value": value, "expiry": expiry}, f)
        except OSError as e:
            logger.error(f"Failed to write cache file {filepath}: {e}")
```

- [ ] **Step 2: Write Resiliency Decorators**

Create `src/crewai_custom_tools/core/decorators.py`:

```python
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional
import requests

logger = logging.getLogger("crewai_custom_tools.decorators")

def api_tool(
    provider: str,
    endpoint: str,
    timeout: float = 30.0,
    default_return: Any = None
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                # Intercept HTTP 429 and retry with exponential backoff
                if e.response is not None and e.response.status_code == 429:
                    logger.warning(f"Rate limited by {provider} {endpoint}. Retrying...")
                    time.sleep(2.0)
                    try:
                        return func(*args, **kwargs)
                    except Exception:
                        pass
                logger.error(f"API Error in {provider} {endpoint}: {e}")
                return default_return or f"Error calling {provider}: {e}"
            except Exception as e:
                logger.error(f"Execution failed in {provider} {endpoint}: {e}")
                return default_return or f"Unexpected failure: {e}"
        return wrapper
    return decorator
```

Create file `src/crewai_custom_tools/core/__init__.py`:

```python
"""Core decorators and base tool definitions."""
from crewai_custom_tools.core.decorators import api_tool
```

- [ ] **Step 3: Run existing cache tests using rtk proxy**

Ensure caching behavior works with the new SHA-256 hashes:

```bash
rtk proxy uv run python -m pytest tests/test_cache.py -v
```

Expected: All caching tests pass successfully.

- [ ] **Step 4: Commit**

```bash
git add src/crewai_custom_tools/config/cache.py src/crewai_custom_tools/core/decorators.py src/crewai_custom_tools/core/__init__.py
git commit -m "feat: implement SHA-256 caching and resiliency decorators"
```

---

### Task 3: Migrate & Centralize Pydantic Models

We will import, consolidate, and export the Pydantic schemas from our source repositories to standardise the data structures used.

**Files:**

- Create: `src/crewai_custom_tools/models/web_search_models.py`
- Create: `src/crewai_custom_tools/models/finance_models.py`
- Create: `src/crewai_custom_tools/models/github_models.py`
- Create: `src/crewai_custom_tools/models/email_models.py`
- Create: `src/crewai_custom_tools/models/rss_models.py`
- Create: `src/crewai_custom_tools/models/airtable_models.py`
- Create: `src/crewai_custom_tools/models/todoist_models.py`
- Create: `src/crewai_custom_tools/models/reports/__init__.py`
- Modify: `src/crewai_custom_tools/models/__init__.py`

**Interfaces:**

- Consumes: Standard Pydantic BaseModel attributes.
- Produces: Reusable models accessible at `crewai_custom_tools.models`.

- [ ] **Step 1: Centralize web and search structures**

Copy and merge models from `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/models/web_search_models.py` into `src/crewai_custom_tools/models/web_search_models.py`.

- [ ] **Step 2: Centralize stock, crypto and market structures**

Copy models from `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/models/finance_models.py` and adapters from `finwiz` into `src/crewai_custom_tools/models/finance_models.py`.

- [ ] **Step 3: Centralize GitHub, Email, RSS, Airtable, and Todoist models**

Copy and populate standard models:

- GitHub models to `src/crewai_custom_tools/models/github_models.py`.
- Email patterns to `src/crewai_custom_tools/models/email_models.py`.
- RSS/OPML schemas to `src/crewai_custom_tools/models/rss_models.py`.
- Airtable schemas to `src/crewai_custom_tools/models/airtable_models.py`.
- Todoist layout models to `src/crewai_custom_tools/models/todoist_models.py`.

- [ ] **Step 4: Update models package exports**

Modify `src/crewai_custom_tools/models/__init__.py` to export everything:

```python
from crewai_custom_tools.models.web_search_models import *
from crewai_custom_tools.models.finance_models import *
from crewai_custom_tools.models.github_models import *
from crewai_custom_tools.models.email_models import *
from crewai_custom_tools.models.rss_models import *
```

- [ ] **Step 5: Run tests to ensure schemas load cleanly**

Verify export schema stability:

```bash
rtk proxy uv run python -m pytest tests/test_exports.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/crewai_custom_tools/models/
git commit -m "feat: migrate and centralize Pydantic models from source codebases"
```

---

### Task 4: Migrate & Unify Web & Search Tools

We will consolidate search and scraper functions into `src/crewai_custom_tools/tools/web/`.

**Files:**

- Create: `src/crewai_custom_tools/tools/web/serper.py`
- Create: `src/crewai_custom_tools/tools/web/scraper.py`
- Create: `src/crewai_custom_tools/tools/web/wikipedia.py`
- Create: `src/crewai_custom_tools/tools/web/rss.py`
- Create: `src/crewai_custom_tools/tools/web/fact_checking.py`
- Modify: `src/crewai_custom_tools/tools/web/__init__.py`
- Create/Copy: `tests/test_web_tools.py`

**Interfaces:**

- Consumes: Unified parameters from `models/web_search_models.py`.
- Produces: Web tools (`PerplexitySearchTool`, `SerperSearchTool`, `UnifiedScraperTool`, `WikipediaTool`, `RSSTool`).

- [ ] **Step 1: Copy and adapt Serper search tool**

Merge `safe_serper.py` and `serper_tool.py` from `menu_planner`/`osint_home` into `src/crewai_custom_tools/tools/web/serper.py`.

- [ ] **Step 2: Unify Scrapers**

Create `src/crewai_custom_tools/tools/web/scraper.py` containing `UnifiedScraperTool` which implements fallback logic: if Javascript or Cloudflare blocks standard BeautifulSoup extraction, automatically route requests through ScrapeNinja proxy or Firecrawl APIs.

- [ ] **Step 3: Port Wikipedia and RSS feeds**

Migrate the tools:

- Wikipedia Search to `src/crewai_custom_tools/tools/web/wikipedia.py`.
- Unified RSS reading & OPML parsing to `src/crewai_custom_tools/tools/web/rss.py`.
- Fact checking utilities to `src/crewai_custom_tools/tools/web/fact_checking.py`.

- [ ] **Step 4: Export web tools**

Modify `src/crewai_custom_tools/tools/web/__init__.py`:

```python
from crewai_custom_tools.tools.web.perplexity import PerplexitySearchTool
from crewai_custom_tools.tools.web.serper import SerperSearchTool
from crewai_custom_tools.tools.web.scraper import UnifiedScraperTool
```

- [ ] **Step 5: Run tests to verify the unified web tools**

Execute web tools test:

```bash
rtk proxy uv run python -m pytest tests/test_perplexity.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/crewai_custom_tools/tools/web/
git commit -m "feat: migrate and unify all web search and scraping tools"
```

---

### Task 5: Migrate & Unify Finance & Crypto Tools

We will centralize Yahoo Finance, CoinMarketCap, Kraken, FRED, and Alpha Vantage tool configurations into `src/crewai_custom_tools/tools/finance/`.

**Files:**

- Create: `src/crewai_custom_tools/tools/finance/company_info.py`
- Create: `src/crewai_custom_tools/tools/finance/history_holdings.py`
- Create: `src/crewai_custom_tools/tools/finance/crypto.py`
- Create: `src/crewai_custom_tools/tools/finance/market_data.py`
- Create: `src/crewai_custom_tools/tools/finance/fear_greed.py`
- Create: `src/crewai_custom_tools/tools/finance/exchange_rate.py`
- Modify: `src/crewai_custom_tools/tools/finance/__init__.py`

**Interfaces:**

- Consumes: Caching (`config/cache.py`) and standard math methods.
- Produces: Financial tools (`YahooFinanceNewsTool`, `YahooFinanceTickerInfoTool`, `CoinMarketCapTool`, `FREDAdapterTool`).

- [ ] **Step 1: Port expanded Yahoo Finance indicators**

Move:

- Company Info metrics tool to `src/crewai_custom_tools/tools/finance/company_info.py`.
- History and ETF holdings to `src/crewai_custom_tools/tools/finance/history_holdings.py`.

- [ ] **Step 2: Port CoinMarketCap and Kraken APIs**

Consolidate historical and real-time listings from `epic_news` into a unified `src/crewai_custom_tools/tools/finance/crypto.py`.

- [ ] **Step 3: Port market indicators, sentiment, and FRED economic data**

Copy:

- FRED indicators to `src/crewai_custom_tools/tools/finance/market_data.py`.
- Fear & Greed indexing scraper to `src/crewai_custom_tools/tools/finance/fear_greed.py`.
- Exchange rate calculations to `src/crewai_custom_tools/tools/finance/exchange_rate.py`.

- [ ] **Step 4: Expose finance imports and run unit tests**

Update exports in `src/crewai_custom_tools/tools/finance/__init__.py`.
Execute:

```bash
rtk proxy uv run python -m pytest tests/test_yfinance_news.py tests/test_yfinance_ticker.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crewai_custom_tools/tools/finance/
git commit -m "feat: consolidate stocks, crypto, and macroeconomic data tools"
```

---

### Task 6: Migrate & Unify OSINT & Cyber Recon Tools

We will migrate deep cyber investigations, domain recon, and French business registers under `src/crewai_custom_tools/tools/osint/`.

**Files:**

- Create: `src/crewai_custom_tools/tools/osint/github.py`
- Create: `src/crewai_custom_tools/tools/osint/email_recon.py`
- Create: `src/crewai_custom_tools/tools/osint/person_recon.py`
- Create: `src/crewai_custom_tools/tools/osint/domain_recon.py`
- Create: `src/crewai_custom_tools/tools/osint/registers.py`
- Create: `src/crewai_custom_tools/tools/osint/__init__.py`
- Create/Copy: `tests/test_osint_tools.py`

**Interfaces:**

- Consumes: `whodap` and `pygithub` clients.
- Produces: OSINT tools (`GitHubTools`, `HunterIoTool`, `FrenchRegistryTool`, `RDAPReconTool`).

- [ ] **Step 1: Move and adapt GitHub tools**

Unify search repositories and organizations into `src/crewai_custom_tools/tools/osint/github.py`.

- [ ] **Step 2: Port email verification and username search**

Write:

- Hunter.io email discoverer to `src/crewai_custom_tools/tools/osint/email_recon.py`.
- Sherlock/Maigret search patterns to `src/crewai_custom_tools/tools/osint/person_recon.py`.

- [ ] **Step 3: Port domain certificates and business registers**

Migrate:

- `crt.sh` and `whodap` RDAP tools into `src/crewai_custom_tools/tools/osint/domain_recon.py`.
- INSEE Sirene, Bodacc, and company registers from `osint_tools` into `src/crewai_custom_tools/tools/osint/registers.py`.

- [ ] **Step 4: Create package init and run OSINT tests**

Verify OSINT tool integrations:

```bash
rtk proxy uv run python -m pytest tests/test_osint_tools.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crewai_custom_tools/tools/osint/
git commit -m "feat: consolidate OSINT, cyber recon, and corporate registries"
```

---

### Task 7: Migrate Report & PDF Document Generators

We will establish template layout builders and HTML-to-PDF compilation under `src/crewai_custom_tools/reporting/`.

**Files:**

- Create: `src/crewai_custom_tools/reporting/pdf_generator.py`
- Create: `src/crewai_custom_tools/reporting/html_generator.py`
- Create: `src/crewai_custom_tools/reporting/template_renderers.py`
- Create: `src/crewai_custom_tools/reporting/__init__.py`

**Interfaces:**

- Consumes: Report objects, HTML styling, Jinja2 template engines.
- Produces: Formatting utilities (`PDFGenerator`, `HTMLDashboardGenerator`, `TemplateRendererFactory`).

- [ ] **Step 1: Port HTML-to-PDF compilers**

Copy and adjust PDF layout engine from `epic_news` to `src/crewai_custom_tools/reporting/pdf_generator.py`.

- [ ] **Step 2: Port Markdown-to-HTML and special template dashboards**

Consolidate dashboard generation templates and Pestel, Financial, HR, and Geospatial Jinja2 renderers from `epic_news` into:

- `src/crewai_custom_tools/reporting/html_generator.py`
- `src/crewai_custom_tools/reporting/template_renderers.py`

- [ ] **Step 3: Run report tests**

Run verification tests for report formatting to ensure layouts load beautifully.
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/crewai_custom_tools/reporting/
git commit -m "feat: migrate rich HTML/PDF document formatting and layout generators"
```

---

### Task 8: Migrate Enterprise APIs & Main Exports

We will finalize Accuweather, Todoist, Airtable, and RAG tools, and expose a clean, public package namespace.

**Files:**

- Create: `src/crewai_custom_tools/enterprise/todoist.py`
- Create: `src/crewai_custom_tools/enterprise/airtable.py`
- Create: `src/crewai_custom_tools/enterprise/accuweather.py`
- Create: `src/crewai_custom_tools/enterprise/rag_tools.py`
- Create: `src/crewai_custom_tools/enterprise/__init__.py`
- Modify: `src/crewai_custom_tools/__init__.py`

**Interfaces:**

- Consumes: Direct API integrations.
- Produces: Enterprise integrations and public endpoints for the full library.

- [ ] **Step 1: Move Airtable, Todoist, and Weather**

Consolidate:

- Todoist list/task integrations to `src/crewai_custom_tools/enterprise/todoist.py`.
- Airtable database readers/writers to `src/crewai_custom_tools/enterprise/airtable.py`.
- Accuweather widgets to `src/crewai_custom_tools/enterprise/accuweather.py`.

- [ ] **Step 2: Migrate RAG Knowledge base adapters**

Copy `save_to_rag_tool.py` and `rag_tools.py` into `src/crewai_custom_tools/enterprise/rag_tools.py`.

- [ ] **Step 3: Expose clean public imports in package root**

Modify `src/crewai_custom_tools/__init__.py` to neatly export all public tools, decorators, and centralized models from one single, clear, namespace.

- [ ] **Step 4: Verify complete, comprehensive test suite pass**

Run our entire suite of 60+ unit tests:

```bash
rtk proxy uv run python -m pytest -v
```

Expected: 100% PASS in < 5 seconds.

- [ ] **Step 5: Commit**

```bash
git add src/crewai_custom_tools/enterprise/ src/crewai_custom_tools/__init__.py
git commit -m "feat: implement enterprise integrations and complete package exports"
```
