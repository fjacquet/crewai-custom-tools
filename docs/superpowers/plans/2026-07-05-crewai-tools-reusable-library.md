# crew-custom-tools Reusable Library Implementation Plan (Migration & Merging Focus)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a lightweight, highly reusable, KIS, DRY, and functionally oriented CrewAI tools library by moving and consolidating existing code and test assets from `epic_news`, `finwiz`, and `osint_tools` into `crew-custom-tools`, rather than reinventing them.

**Architecture:** Consolidate duplicated files from the source directories, clean up local package import prefixes, expose clean functional helper methods, and preserve existing mock tests.

**Tech Stack:** Python 3.11+, `uv` (workspace package builder), `crewai>=0.100.0`, `requests`, `pydantic>=2.0.0`, `beautifulsoup4`, `yfinance`.

## Global Constraints
- Do not write tools from scratch; copy them from `/Users/fjacquet/Projects/crews/epic_news/`, `/Users/fjacquet/Projects/finwiz/`, or `/Users/fjacquet/Projects/osint_tools/`.
- Change local project-level imports (like `from epic_news.utils...` or `from finwiz.infrastructure...`) to use standardized local package imports or standalone helper structures.
- Standardize on `requests` and resilient decorators.

---

### Task 1: Scaffolding & Packaging Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/crew_custom_tools/__init__.py`
- Create: `README.md`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write pyproject.toml and README.md**

Create `/Users/fjacquet/Projects/crew-custom-tools/pyproject.toml`:
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
    "crewai>=0.100.0",
    "requests>=2.31.0",
    "pydantic>=2.0.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
finance = [
    "yfinance>=0.2.38",
]

[tool.hatch.build.targets.wheel]
packages = ["src/crew_custom_tools"]
```

Create `/Users/fjacquet/Projects/crew-custom-tools/README.md`:
```markdown
# crew-custom-tools
Centralized resilient tools for CrewAI.
```

- [ ] **Step 2: Create directories and initialize package**

Create directory `src/crew_custom_tools` and write `/Users/fjacquet/Projects/crew-custom-tools/src/crew_custom_tools/__init__.py`:
```python
"""Centralized CrewAI tools library."""

__version__ = "0.1.0"
```

Create `tests/__init__.py`.

- [ ] **Step 3: Verify uv can install the package**

Run:
```bash
uv pip install -e .
```
Expected: Success

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml README.md src/crew_custom_tools/__init__.py
git commit -m "chore: scaffold project structure"
```

---

### Task 2: Migrate and Centralize the Caching Layer

We will copy the caching mechanisms from `epic_news` to establish a shared caching layer for the library.

**Files:**
- Copy: `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/cache_manager.py` -> `src/crew_custom_tools/config/cache.py`
- Copy: `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_cache_manager.py` (if any) or port caching tests.

- [ ] **Step 1: Move and adapt cache_manager.py**

Copy `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/cache_manager.py` into `src/crew_custom_tools/config/cache.py` and modify imports. If it imports from `epic_news.utils.logger`, change it to standard `logging` or create a standalone functional logger to keep the library simple and self-contained.

- [ ] **Step 2: Port existing cache tests**

Copy and run test suite:
```bash
uv run pytest tests/test_cache.py -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/crew_custom_tools/config/cache.py tests/test_cache.py
git commit -m "feat: migrate and adapt caching layer"
```

---

### Task 3: Migrate and Standardize the `PerplexitySearchTool`

**Files:**
- Copy: `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/perplexity_search_tool.py` -> `src/crew_custom_tools/tools/web/perplexity.py`
- Copy: `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_perplexity_search_tool.py` -> `tests/test_perplexity.py`

- [ ] **Step 1: Move perplexity_search_tool.py**

Copy file `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/perplexity_search_tool.py` into `src/crew_custom_tools/tools/web/perplexity.py`.
Modify imports:
- Replace `from epic_news.utils.logger import get_logger` with standard python `logging.getLogger`.

- [ ] **Step 2: Move and adjust tests**

Copy `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_perplexity_search_tool.py` into `tests/test_perplexity.py`. Adjust imports inside the test file to point to `crew_custom_tools.tools.web.perplexity`.

- [ ] **Step 3: Run the tests to confirm they pass**

Run:
```bash
uv run pytest tests/test_perplexity.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/crew_custom_tools/tools/web/perplexity.py tests/test_perplexity.py
git commit -m "feat: migrate and standardize PerplexitySearchTool and tests"
```

---

### Task 4: Migrate and Standardize Yahoo Finance News Tool

**Files:**
- Copy: `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/yahoo_finance_news_tool.py` -> `src/crew_custom_tools/tools/finance/yfinance_news.py`
- Copy: `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_yahoo_finance_news_tool.py` -> `tests/test_yfinance_news.py`

- [ ] **Step 1: Move yahoo_finance_news_tool.py**

Copy `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/yahoo_finance_news_tool.py` into `src/crew_custom_tools/tools/finance/yfinance_news.py`.
Modify imports:
- Replace `from epic_news.tools.cache_manager import get_cache_manager` with `from crew_custom_tools.config.cache import get_cache_manager` (or your mapped caching module).
- Replace `from epic_news.models.finance_models import GetTickerNewsInput` with a local Pydantic schema declaration within `yfinance_news.py` to keep it standalone and simple (KISS/DRY).

- [ ] **Step 2: Move and adjust tests**

Copy `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_yahoo_finance_news_tool.py` into `tests/test_yfinance_news.py`. Adjust imports inside the test file to point to `crew_custom_tools.tools.finance.yfinance_news`.

- [ ] **Step 3: Run tests to confirm they pass**

Run:
```bash
uv run pytest tests/test_yfinance_news.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/crew_custom_tools/tools/finance/yfinance_news.py tests/test_yfinance_news.py
git commit -m "feat: migrate and standardize YahooFinanceNewsTool and tests"
```

---

### Task 5: Migrate and Standardize Yahoo Finance Ticker Info Tool

**Files:**
- Copy: `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/yahoo_finance_ticker_info_tool.py` -> `src/crew_custom_tools/tools/finance/yfinance_ticker.py`
- Copy: `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_yahoo_finance_ticker_info_tool.py` -> `tests/test_yfinance_ticker.py`

- [ ] **Step 1: Move yahoo_finance_ticker_info_tool.py**

Copy `/Users/fjacquet/Projects/crews/epic_news/src/epic_news/tools/yahoo_finance_ticker_info_tool.py` into `src/crew_custom_tools/tools/finance/yfinance_ticker.py`.
Modify imports:
- Replace cache manager imports with `crew_custom_tools.config.cache`.
- Inline the local `GetTickerInfoInput` Pydantic model directly into `yfinance_ticker.py` to keep it completely self-contained.

- [ ] **Step 2: Move and adjust tests**

Copy `/Users/fjacquet/Projects/crews/epic_news/tests/tools/test_yahoo_finance_ticker_info_tool.py` into `tests/test_yfinance_ticker.py`. Adjust imports inside the test to target `crew_custom_tools.tools.finance.yfinance_ticker`.

- [ ] **Step 3: Run tests to confirm they pass**

Run:
```bash
uv run pytest tests/test_yfinance_ticker.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/crew_custom_tools/tools/finance/yfinance_ticker.py tests/test_yfinance_ticker.py
git commit -m "feat: migrate and standardize YahooFinanceTickerInfoTool and tests"
```

---

### Task 6: Expose Imports at Package Root

**Files:**
- Modify: `src/crew_custom_tools/__init__.py`
- Create: `tests/test_exports.py`

- [ ] **Step 1: Expose top-level exports**

Modify `src/crew_custom_tools/__init__.py` to export the migrated tools so users can import them directly from `crew_custom_tools`:
```python
"""Centralized CrewAI tools library."""

__version__ = "0.1.0"

from crew_custom_tools.tools.web.perplexity import PerplexitySearchTool
from crew_custom_tools.tools.finance.yfinance_ticker import YahooFinanceTickerInfoTool
from crew_custom_tools.tools.finance.yfinance_news import YahooFinanceNewsTool

__all__ = [
    "PerplexitySearchTool",
    "YahooFinanceTickerInfoTool",
    "YahooFinanceNewsTool",
]
```

- [ ] **Step 2: Create a top-level smoke test**

Create `tests/test_exports.py` to verify exports:
```python
def test_exports():
    from crew_custom_tools import PerplexitySearchTool, YahooFinanceTickerInfoTool, YahooFinanceNewsTool
    assert PerplexitySearchTool is not None
    assert YahooFinanceTickerInfoTool is not None
    assert YahooFinanceNewsTool is not None
```

- [ ] **Step 3: Run full suite to ensure 100% success**

Run:
```bash
uv run pytest -v
```
Expected: 100% tests PASSing

- [ ] **Step 4: Commit**

```bash
git add src/crew_custom_tools/__init__.py tests/test_exports.py
git commit -m "feat: finalize package bundling and exports"
```
