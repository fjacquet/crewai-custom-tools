# `crew-custom-tools` User Guide

Welcome to the **`crew-custom-tools`** library! This guide outlines how to install the package, import and configure unified tools, leverage our persistent caching layer, and migrate your existing projects (`epic_news`, `finwiz`, and `osint_tools`) cleanly.

---

## 1. Installation

The package is built to use `uv` for lightning-fast environment setup. Choose the installation method that fits your project.

### 1.1 Local Development (Editable Mode)
To work on `crew-custom-tools` and have your changes instantly reflected in your agent project, use `uv` editable mode:
```bash
# Inside epic_news, finwiz, or osint_tools
uv add --editable /Users/fjacquet/Projects/crewai-tools
```

### 1.2 Installing Modular Extras
To keep dependencies lightweight, we utilize Python's Package Extras.

- **For general web/search tools only (like `osint_tools`)**:
  ```bash
  uv add "crew-custom-tools @ file:///Users/fjacquet/Projects/crewai-tools"
  ```
- **For financial tools (like `finwiz`)** (installs `yfinance`):
  ```bash
  uv add "crew-custom-tools[finance] @ file:///Users/fjacquet/Projects/crewai-tools"
  ```
- **For development/testing dependencies** (installs `pytest-mock`):
  ```bash
  uv add "crew-custom-tools[dev] @ file:///Users/fjacquet/Projects/crewai-tools"
  ```

---

## 2. Exposing the Unified Tools

All core tools can be imported directly from the top-level namespace:
```python
from crew_custom_tools import (
    PerplexitySearchTool,
    YahooFinanceTickerInfoTool,
    YahooFinanceNewsTool
)
```

### 2.1 `PerplexitySearchTool`
Use this tool to run resilient web-grounded AI-synthesized queries with citation extraction.

```python
import os
from crew_custom_tools import PerplexitySearchTool

# Ensure PPLX_API_KEY or PERPLEXITY_API_KEY is in your environment
os.environ["PERPLEXITY_API_KEY"] = "your_key_here"

# Configure to output JSON or Markdown
tool = PerplexitySearchTool(output_format="markdown", model="sonar-pro")

# Run search query
result = tool._run(query="Latest developments in fusion energy July 2026", focus="news", recency="week")
print(result)
```

### 2.2 `YahooFinanceNewsTool`
Fetches a list of recent news for any ticker symbol, automatically integrated with caching to avoid rate limits.

```python
from crew_custom_tools import YahooFinanceNewsTool

# Instantiates tool with a 15-minute caching TTL
tool = YahooFinanceNewsTool(caching=True, ttl=900)

news_json = tool._run(ticker="AAPL", limit=3)
print(news_json)
```

### 2.3 `YahooFinanceTickerInfoTool`
Retrieves key metric statistics (P/E ratio, current price, volume, previous close, sector) for stocks, ETFs, and cryptos.

```python
from crew_custom_tools import YahooFinanceTickerInfoTool

tool = YahooFinanceTickerInfoTool(caching=True, ttl=1800)

metrics_json = tool._run(ticker="TSLA")
print(metrics_json)
```

---

## 3. Utilizing the Caching Layer

Our library features a thread-safe, persistence-deterministic, and self-healing caching layer.

### 3.1 Custom Caching on Functions (`@cache_api_call`)
You can decorate any API/IO function to automatically cache its results based on input parameters.

```python
from crew_custom_tools.config.cache import cache_api_call

@cache_api_call(key="external_service_lookup", ttl=600)
def fetch_user_data(user_id: int, include_metadata: bool = True):
    # This side-effect function will execute once per unique arguments combo, 
    # caching the result inside '.cache/' for 10 minutes.
    print(f"Fetching data from external API for {user_id}...")
    return {"user_id": user_id, "status": "active"}
```

*Note: `@cache_api_call` is fully compatible with class instance methods. It automatically strips/ignores the dynamic memory address of `self` so that cache keys are completely deterministic across separate script runs and instantiations.*

### 3.2 Programmatic Cache Cleaning
```python
from crew_custom_tools.config.cache import get_cache_manager

cache = get_cache_manager()

# Clear ALL cached entries
cache.clear()

# Clear only entries that have exceeded their TTL
expired_count = cache.clear_expired()
print(f"Removed {expired_count} expired entries.")
```

---

## 4. Migration Walkthrough for Existing Projects

### 4.1 Migrating `epic_news`
1. Run `uv add "crew-custom-tools[finance] @ file:///Users/fjacquet/Projects/crewai-tools"` inside `epic_news`' directory.
2. In your crews or models, replace:
   ```python
   from epic_news.tools.perplexity_search_tool import PerplexitySearchTool
   from epic_news.tools.yahoo_finance_news_tool import YahooFinanceNewsTool
   from epic_news.tools.cache_manager import get_cache_manager
   ```
   with:
   ```python
   from crew_custom_tools import PerplexitySearchTool, YahooFinanceNewsTool
   from crew_custom_tools.config.cache import get_cache_manager
   ```
3. Delete the duplicated local files from `src/epic_news/tools/` folder:
   - `perplexity_search_tool.py`
   - `yahoo_finance_news_tool.py`
   - `yahoo_finance_ticker_info_tool.py`
   - `cache_manager.py`

### 4.2 Migrating `finwiz`
1. Run `uv add "crew-custom-tools[finance] @ file:///Users/fjacquet/Projects/crewai-tools"` inside `finwiz`' directory.
2. Replace:
   ```python
   from finwiz.tools.perplexity_search_tool import PerplexitySearchTool
   from finwiz.tools.yahoo_finance_news_tool import YahooFinanceNewsTool
   ```
   with:
   ```python
   from crew_custom_tools import PerplexitySearchTool, YahooFinanceNewsTool
   ```
3. Safely delete duplicated python files from local `/tools/` folder.
