# ADR 0001: Core Architecture & Design Choices (Extras Era)

**Date**: 2026-07-05
**Author**: Gemini CLI & Collaborative Engineering Team
**Status**: SUPERSEDED BY [ADR-0002](0002-universal-monolith.md)

---

## Context & Problem Statement

We had massive code duplication across three independent multi-agent repositories (`epic_news`, `finwiz`, and `osint_tools`). Tools like Perplexity search, Yahoo Finance News, and Yahoo Finance Ticker Info were copied and slightly modified in each codebase. This caused diverging features, highly fragmented caching systems, unstable rate-limiting strategies, and massive development overhead.

We needed a centralized Python library that consolidates these implementations without imposing heavy, unused dependencies on simple projects (e.g. installing `yfinance` in a project that only needs Perplexity search).

---

## Considered Alternatives

1. **Mono-repo with Shared Python Paths**: Import files directly using relative filesystem paths.
   - *Verdict*: Rejected. Breaks isolation, hinders standalone Docker containerization, and is highly fragile to folder restructuring.
2. **Standard Centralized Package on PyPI**: Publish to a public PyPI repository.
   - *Verdict*: Rejected. The library name `crewai-tools` was already taken, and public registry exposure of internal bespoke tools is undesired.
3. **Local/Git-Based Modular Package (`crewai-custom-tools`)** [Chosen]: Set up a clean Python package structure with custom optional dependency Extras, making it installable locally in editable mode (`uv pip install -e .`) or directly from a private Git repository.

---

## Architectural Decisions

### Decision 1: Modular Packaging via Dependency Extras

- **Details**: We declared `yfinance` as an optional dependency extra `[finance]` and `pytest-mock` under `[dev]`. Only base essentials (`crewai`, `requests`, `pydantic`, `beautifulsoup4`) are required by default.
- **Rationale**: Keeps base dependencies extremely small, allowing lightweight projects like `osint_tools` to run without pulling heavy scientific or charting dependencies, while `finwiz` can easily opt-in via `crewai-custom-tools[finance]`.

### Decision 2: Functional Programming Design Principles (KISS / DRY)

- **Details**: We avoid deep class-inheritance hierarchies. Within the tools, we explicitly separated side-effects (calling APIs) from pure data transformation functions (mapping fields and cleaning dictionaries), making the logic highly readable and easily unit-testable.
- **Rationale**: Functional blocks are easier to reason about, heavily reduce cognitive load, and can be tested deterministically using standard unit tests and mocks.

### Decision 3: Deterministic Cache Keys & Dynamic `self` Exclusion

- **Details**: Built-in Python `hash()` is randomized on every process restart, causing saved `.json` caches to be orphaned. We replaced it with a deterministic hashing flow using `hashlib.sha256`.
- Additionally, if the decorator `@cache_api_call` is wrapped around an instance method, the first argument (`args[0]`) is the instance `self`, which by default has a string representation containing a dynamic memory address (e.g. `<... object at 0x10bfaef50>`). We implemented an inspector in `cache.py` to strip/mask `self`'s address, replacing the instance argument with its class name.
- **Rationale**: Prevents cache invalidation between runs and guarantees that identical calculations across different instantiations of a tool hit the exact same cache.

### Decision 4: Concurrency-Safe, Self-Healing Cache Operations

- **Details**: File system writes are handled with try-except blocks, and unlinks safely catch `FileNotFoundError`. If a cache file is corrupted or malformed, the system automatically deletes it and returns `None` instead of crashing.
- **Rationale**: Prevents multi-threaded or multi-process agent environments from throwing unhandled `FileNotFoundError` or `JSONDecodeError` during race conditions on expired files.

### Decision 5: Non-Caching of API Failures and Exceptions

- **Details**: Refactored tools like `YahooFinanceNewsTool` to ensure that standard API calls cache successful responses, but `except Exception` blocks never write failure objects to the persistent cache folder.
- **Rationale**: If an API request fails due to temporary network blips, API rate limits, or transient gateway errors, caching the error would lock the system in a failing state for the duration of the TTL. Not caching errors ensures that the next execution can immediately recover when the external service becomes healthy.

---

## Implications & Consequences

- **Local Linkability**: Downstream projects must execute `uv add --editable /path/to/crewai-tools` or pull using standard `[extra]` brackets.
- **Import Changes**: Downstream codebases must update their import statements from `epic_news.tools.cache_manager` or similar to `from crewai_custom_tools.config.cache import get_cache_manager`.
- **Improved Security and Isolation**: Testing and verifying tools is now completely decoupled from agent orchestrators.
