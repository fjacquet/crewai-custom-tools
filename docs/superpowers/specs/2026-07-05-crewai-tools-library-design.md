# Design Specification: Centralized CrewAI Tools Library (`crewai-custom-tools`)

**Date**: 2026-07-05
**Status**: APPROVED / PENDING IMPLEMENTATION PLAN
**Author**: Gemini CLI

---

## 1. Executive Summary

This document specifies the design for a centralized, reusable CrewAI tools library (`crewai-custom-tools`). The library consolidates overlapping, duplicated tools currently spread across three repositories:

1. `/Users/fjacquet/Projects/crews/epic_news`
2. `/Users/fjacquet/Projects/finwiz`
3. `/Users/fjacquet/Projects/osint_tools`

By extracting and unifying these tools, we eliminate code duplication, standardize resilience features (like exponential backoff, rate limiting, and timeouts), and enable optional, performant caching.

---

## 2. Packaging and Installation Strategy (`uv`)

We will package the library as a standard, modular Python package using `uv`. To prevent installing heavy, unnecessary packages in projects that do not use them, the library will leverage Python's `optional-dependencies` (extras).

### 2.1 `pyproject.toml` Structure

The package is named `crewai-custom-tools` (or imports as `crewai_custom_tools`).

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
    "crewai>=0.100.0",
    "requests>=2.31.0",
    "pydantic>=2.0.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
finance = [
    "yfinance>=0.2.38",
]
osint = [
    "pygithub>=2.2.0",
]
all = [
    "yfinance>=0.2.38",
    "pygithub>=2.2.0",
]
```

### 2.2 Project-Level Installation via `uv`

During development, the library can be linked locally in "editable" mode for immediate hot-reloading:

```bash
# Inside any of the three consumer repositories
uv add --editable /Users/fjacquet/Projects/crewai-custom-tools
```

For production deployment or remote team access, the consumer projects can declare a direct dependency pointing to the GitHub repository:

```toml
# Inside pyproject.toml of epic_news, finwiz, or osint_tools
crewai-custom-tools = { git = "https://github.com/fjacquet/crewai-custom-tools.git", tag = "v0.1.0" }
```

To install specific extras:

```bash
# For finwiz
uv add "crewai-custom-tools[finance] @ git+https://github.com/fjacquet/crewai-custom-tools.git"

# For osint_tools
uv add "crewai-custom-tools[osint] @ git+https://github.com/fjacquet/crewai-custom-tools.git"
```

---

## 3. Library Directory Structure

```text
crewai-custom-tools/
├── pyproject.toml                 # Package definition and dependencies
├── README.md                      # Usage documentation
├── src/
│   └── crewai_custom_tools/
│       ├── __init__.py            # Clean exports of unified tools
│       ├── core/                  # Core abstractions and decorators
│       │   ├── __init__.py
│       │   ├── base_tool.py       # Base class handling common configuration
│       │   └── decorators.py      # Resiliency, retry, and rate limiting (@api_tool)
│       ├── config/                # Caching and global endpoints
│       │   ├── __init__.py
│       │   └── cache.py           # Standardized cache manager
│       └── tools/                 # The unified tools
│           ├── __init__.py
│           ├── web/               # General Web & Search tools
│           │   ├── __init__.py
│           │   ├── perplexity.py  # Unified Perplexity search
│           │   ├── tavily.py
│           │   └── scrapers.py    # Consolidated scraper & crawl tools
│           ├── finance/           # yfinance & crypto tools (Requires [finance])
│           │   ├── __init__.py
│           │   ├── yfinance_ticker.py
│           │   ├── yfinance_news.py
│           │   ├── alpha_vantage.py
│           │   └── kraken.py
│           └── osint/             # OSINT / general tools (Requires [osint])
│               ├── __init__.py
│               ├── github.py
│               └── hunter_io.py
└── tests/                         # Ported and consolidated test suite
    ├── conftest.py
    ├── test_cache.py
    ├── test_perplexity.py
    └── ...
```

---

## 4. Key Architectural Integrations

### 4.1 Resilience Decorators (`core/decorators.py`)

We adopt the advanced `@api_tool` decorator from `finwiz` and place it in `core/decorators.py`. It provides standard retry mechanisms, timeout configurations, and fail-safe return behaviors:

```python
import time
from functools import wraps
from typing import Any, Callable

def api_tool(
    provider: str,
    endpoint: str,
    timeout: float = 30.0,
    default_return: Any = None
) -> Callable:
    """
    Decorator that injects standard error boundary handling, timeouts,
    automatic logging, and basic retry-upon-rate-limit logic.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Handle rate limiting / retry logic
            # Handle timeout enforcement
            # Catches requests.RequestException cleanly and logs errors
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log error with a standardized logger
                if default_return is not None:
                    return default_return
                raise e
        return wrapper
    return decorator
```

### 4.2 Caching Framework (`config/cache.py`)

We port `epic_news`'s highly performant caching manager into the library core. The cache manager supports TTL-based memory and disk-based caches:

* Consumer projects can supply their own cache directories or use a default standard directory (`.crewai_cache/`).
* Tools that support caching can enable it via constructor arguments (e.g. `caching=True`, `ttl=900`).

---

## 5. Unified Tool Specifications

### 5.1 `PerplexitySearchTool`

Unified version of Perplexity Search, marrying `epic_news`'s focus modes with `finwiz`'s rate-limiting, custom system roles, and model selectors.

* **Attributes**:
  * `output_format`: `"json"` (for parsed workflows in `epic_news`/`osint_tools`) or `"markdown"` (for generation in `finwiz`).
  * `model`: Default `"sonar-pro"`.
  * `api_key`: Validates both `PERPLEXITY_API_KEY` and `PPLX_API_KEY`.
  * Checks/fails-fast upon instantiation.

* **Interface**:

  ```python
  from crewai.tools import BaseTool
  from pydantic import BaseModel, Field

  class PerplexitySearchInput(BaseModel):
      query: str = Field(..., description="The search query")
      focus: str = Field("internet", description="Focus mode: internet, academic, news, reddit")
      recency: str = Field("week", description="Recency filter: day, week, month")

  class PerplexitySearchTool(BaseTool):
      name: str = "perplexity_search"
      description: str = "Resilient web search using Perplexity API."
      args_schema: type[BaseModel] = PerplexitySearchInput

      output_format: str = "markdown"  # "markdown" or "json"
      model: str = "sonar-pro"

      # Runs within @api_tool decorator
      def _run(self, query: str, focus: str = "internet", recency: str = "week") -> str:
          ...
  ```

### 5.2 `YahooFinanceTickerInfoTool`

Consolidates the basic information lookup from `epic_news` with the extensive fundamental metrics of `finwiz` (beta, debt-to-equity, total assets, nav, expense ratio, timestamping).

* **Features**:
  * Customizable cache support (via `caching=True` and `ttl=1800`).
  * Supports `prefetched_data` to support batch queries.
  * Adds real-time source markers (`live_api` or `prefetched`) to the metadata dictionary output.

### 5.3 `YahooFinanceNewsTool`

Consolidates yfinance news lookup.

* **Features**:
  * Merges the JSON output caching from `epic_news` with clean Markdown formatting options.
  * `output_format`: Customizable via `"markdown"` or `"json"`.

---

## 6. Verification and Testing Strategy

1. **Test Porting**:
   We will port existing unit tests from `/Users/fjacquet/Projects/crews/epic_news/tests/tools` and `/Users/fjacquet/Projects/finwiz/src/finwiz/tests` into the `crewai-custom-tools/tests` directory.
2. **Environment Simulation**:
   Tests will mock API calls (Perplexity, yfinance, GitHub) using `pytest-mock` or standard unit test patch decorators to ensure deterministic, token-free test execution.
3. **Execution**:
   Using `uv run pytest`, we will run the entire suite in the new library to guarantee that every single extracted tool passes 100% of its contract criteria.

---

## 7. Migration Plan for Existing Repositories

Once the library is completed and verified:

1. **Repository Dependency Setup**:
   Add `crewai_custom_tools` to consumer repositories (`epic_news`, `finwiz`, `osint_tools`) with standard or extra dependency flags.
2. **Import Modification**:
   Replace local imports like:
   `from epic_news.tools.perplexity_search_tool import PerplexitySearchTool`
   with:
   `from crewai_custom_tools import PerplexitySearchTool`
3. **Remove Old Code**:
   Safely delete duplicate Python files from local repository `/tools` folders.
