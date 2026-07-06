# Architecture Decision Record (ADR) 0001: Core Architecture & Design Choices

**Date**: 2026-07-05  
**Author**: Gemini CLI & Collaborative Engineering Team  
**Status**: APPROVED / MAINTAINED  

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
3. **Local/Git-Based Modular Package (`crew-custom-tools`)** [Chosen]: Set up a clean Python package structure making it installable locally in editable mode (`uv pip install -e .`) or directly from a private Git repository.

---

## Architectural Decisions

### Decision 1: Transition to the Universal Monolith Pattern (Approach A)
- **Details**: While we initially considered modular Python Extras, we transitioned to a **Universal Monolith** design. All 30+ tools (including Stocks, Cryptos, OSINT, Document Builders, and Enterprise APIs) are fully integrated into core dependencies.
- To prevent C-library compilation failures during installation (e.g. `ta-lib` or `quantlib`), all quantitative metrics and financial math are written using pure Python, pandas, and numpy fallbacks.
- **Rationale**: Drastically simplifies library packaging and deployment. Consumers can install the package once and have full access to all 30+ tools out of the box with zero runtime setup or module-not-found errors.

### Decision 2: Functional Programming Design Principles (KISS / DRY)
- **Details**: We avoid deep class-inheritance hierarchies. Within the tools, we explicitly separated side-effects (calling APIs) from pure data transformation functions (mapping fields and cleaning dictionaries), making the logic highly readable and easily unit-testable.
- **Rationale**: Functional blocks are easier to reason about, heavily reduce cognitive load, and can be tested deterministically using standard unit tests and mocks.

### Decision 3: Deterministic Cache Keys & Dynamic `self` Exclusion (SHA-256)
- **Details**: Standard Python `hash()` is randomized on every process restart, causing saved `.json` caches to be orphaned. We replaced it with a deterministic hashing flow using **`hashlib.sha256`** truncated to 32 characters for safe filenames on all OS platforms (completely removing weak MD5 keying).
- Additionally, if the decorator `@cache_api_call` is wrapped around an instance method, the first argument (`args[0]`) is the instance `self`, which by default has a string representation containing a dynamic memory address (e.g. `<... object at 0x10bfaef50>`). We implemented an inspector in `cache.py` to strip/mask `self`'s address, replacing the instance argument with its class name.
- **Rationale**: Prevents cache invalidation between runs, avoids security warnings from weak hashing algorithms, and guarantees that identical calculations across different instantiations of a tool hit the exact same cache.

### Decision 4: Concurrency-Safe, Self-Healing Cache Operations
- **Details**: File system writes are handled with try-except blocks, and unlinks safely catch `FileNotFoundError`. If a cache file is corrupted or malformed, the system automatically deletes it and returns `None` instead of crashing.
- **Rationale**: Prevents multi-threaded or multi-process agent environments from throwing unhandled `FileNotFoundError` or `JSONDecodeError` during race conditions on expired files.

### Decision 5: Non-Caching of API Failures and Exceptions
- **Details**: Refactored tools to ensure that standard API calls cache successful responses, but `except Exception` blocks never write failure objects to the persistent cache folder.
- **Rationale**: If an API request fails due to temporary network blips, API rate limits, or transient gateway errors, caching the error would lock the system in a failing state for the duration of the TTL. Not caching errors ensures that the next execution can immediately recover when the external service becomes healthy.

### Decision 6: Native Model Context Protocol (MCP) Server Integration
- **Details**: We integrated **FastMCP** inside `crew_custom_tools/mcp_server.py` to automatically wrap and expose our consolidated tools directly to any standard MCP client (Cursor, Windsurf, Claude Desktop, etc.). We registered this as an official console script `crew-custom-tools-mcp` inside `pyproject.toml`.
- **Rationale**: Seamlessly expands our toolkit from being a CrewAI-only library to a global tool provider that can be used directly inside modern AI developer editors and chat interfaces natively.

### Decision 7: Natively Hosted GitHub Pages Documentation (No gh-pages branch)
- **Details**: Migrated our `.github/workflows/docs.yml` deployment from using a separate `gh-pages` branch to using **native GitHub Actions Pages deployments**. The workflow builds the MkDocs material site, uploads the folder as a secure pages artifact, and deploys it natively via GitHub's official pages API.
- **Rationale**: Keeps our repository's git branch structure 100% pristine and clean, eliminating git history bloat and keeping all publication pipelines completely native to GitHub Actions.

### Decision 8: Hybrid API Authentication (Free Fallback + Paid Upgrade)
- **Details**: For external scrapers/APIs (like Epieos, OpenCorporates, and ScrapeNinja), the tools are designed as a hybrid: they support a keyless/free scraping fallback mode by default (enabling immediate use out of the box), and automatically upgrade to use official high-speed paid endpoints when an API key is supplied in the environment.
- **Rationale**: Ensures the tools are accessible and usable with zero initial configuration, while allowing enterprise-grade reliability and speed upscales when API keys are available.

---

## Implications & Consequences

- **Local Linkability**: Downstream projects must execute `uv add --editable /path/to/crew_custom_tools`.
- **Import Changes**: Downstream codebases must update their import statements to `from crew_custom_tools import ...`.
- **Improved Security and Isolation**: Testing and verifying tools is now completely decoupled from agent orchestrators.
- **Pristine Branching**: The repository maintains only a single `main` branch with no automated branch pollution.
