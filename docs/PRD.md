# Product Requirements Document (PRD): `crewai-custom-tools`

**Status**: APPROVED
**Version**: 1.0
**Target Release**: v0.1.0 (Initial Consolidative Release)

---

## 1. Product Vision

Multi-agent frameworks like CrewAI rely heavily on specific, performant, and resilient tools to fetch information and interact with external systems. Historically, three separate agent repositories (`epic_news`, `finwiz`, and `osint_tools`) maintained duplicated, slightly divergent versions of identical tools (e.g., Perplexity Search, Yahoo Finance News, Ticker Info). This duplication led to fragmented improvements, high maintenance overhead, and inconsistent resilience (such as rate limits causing unexpected agent crashes).

The goal of `crewai-custom-tools` is to consolidate these duplicated utilities into a **highly reusable, lightweight, resilient, and standardized** local package. By separating the tools library from individual agent configurations, we achieve clean engineering boundaries, simplify codebases, and ensure that any core tool optimization immediately benefits all downstream projects.

---

## 2. Core Objectives

1. **Zero Duplication (DRY)**: Centralize overlapping tools (Perplexity and Yahoo Finance) into a single installable package.
2. **KISS & Functional Focus**: Keep code structures extremely simple, avoiding deep inheritance chains. Isolate side-effects (API queries, file operations) into pure, composable helper functions.
3. **Resilience & Fault Tolerance**: Wrap all network-bound API queries in robust retry-upon-rate-limit logic with exponential backoff and safe default fallbacks.
4. **Deterministic Caching**: Provide a shared, performant, and thread-safe TTL caching system that persists reliably across process restarts.
5. **Lightweight Profile**: Implement modular dependencies ("Extras") so that a lightweight general-purpose project (like `osint_tools`) is not forced to install large financial packages (like `yfinance`) unless it explicitly opts in.

---

## 3. Targeted Capabilities (v0.1.0)

### 3.1 Core Architecture & Decorators

- **Standardized Caching Layer (`config/cache.py`)**: A file-system and in-memory TTL caching manager.
  - Automatically handles `json.JSONDecodeError` or corrupted files gracefully by purging them and failing-safe.
  - Uses a deterministic hash generator combining key prefixes with MD5 digests to avoid file collisions or exceeding OS-level filename limits.
- **Function Caching Decorator (`@cache_api_call`)**: Automatically caches synchronous function results. Employs `hashlib.sha256` serialization instead of non-deterministic Python `hash()`, preserving cache hits across process restarts and maintaining proper function metadata via `functools.wraps`.
- **Resilient API Handling**: Implements standardized retry logic and exponential backoff.

### 3.2 Unified Tool Suite

- **`PerplexitySearchTool` (`tools/web/perplexity.py`)**:
  - Unified search interface supporting customizable search focus modes (`internet`, `news`, `academic`, `reddit`).
  - Supports dual return schemas: `"json"` (for downstream parsing engines) or `"markdown"` (for human-readable agent reports).
  - Handles API keys flexibly, recognizing both `PPLX_API_KEY` and `PERPLEXITY_API_KEY` environment variables.
- **`YahooFinanceNewsTool` (`tools/finance/yfinance_news.py`)**:
  - Fetches recent news headlines, publishers, and publication timestamps.
  - Features configurable limits and outputs in structured json format.
- **`YahooFinanceTickerInfoTool` (`tools/finance/yfinance_ticker.py`)**:
  - Extracts and formats a standardized subset of key stock/ETF metrics (P/E ratio, market cap, beta, previous close, current price).
  - Integrates caching directly to respect yfinance rate limitations.

---

## 4. Architectural Boundaries and Constraints

- **Language**: Python 3.11+
- **Dependency Manager**: `uv` (pip-compatible Hatchling backend)
- **CrewAI Version floor**: `crewai>=0.100.0`
- **Testing Standard**: Complete, high-signal mock-based tests using `pytest` and `pytest-mock` (no system-wide dependencies required during tests).
- **Security Constraint**: Absolutely no hardcoded secrets or production credentials may ever be committed. API keys must reside strictly in environment variables.

---

## 5. Success Criteria

- **100% Passing Tests**: All 40 unit and integration tests must execute and pass in under 5 seconds.
- **Dramatically Lower Maintenance Overhead**: Safely delete duplicated python scripts across `/tools` directories in `epic_news`, `finwiz`, and `osint_tools` post-integration.
- **Consistent Execution**: API rate limits or transient errors must be handled gracefully without ever crashing agent routines.
