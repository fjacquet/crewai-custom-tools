# ADR 0002: Transition to the Universal Monolith Pattern (Approach A)

**Date**: 2026-07-05
**Author**: Gemini CLI & Collaborative Engineering Team
**Status**: ACCEPTED
**Supersedes**: Decision 1 in [ADR-0001](0001-core-architecture-and-design.md)

---

## Context & Problem Statement

In [ADR-0001](0001-core-architecture-and-design.md), we designed a modular packaging structure with Python Extras to keep the base package installation extremely light. However, as the number of consolidated tools grew (to over 30+ tools across Web, Finance, OSINT, and Reporting), managing optional extra dependency groups created runtime configuration overhead and dependency resolution fragmentation for downstream users.

We needed a simpler, bulletproof packaging standard that guarantees all tools work flawlessly out of the box with zero runtime "ModuleNotFoundError" exceptions.

---

## Considered Alternatives

1. **Keep Python Extras Bracket groups**: Require downstream users to specify `crewai-custom-tools[finance,osint]`.
   - *Verdict*: Rejected. Highly prone to configuration errors; users frequently forget brackets, leading to runtime failures inside Docker containers.
2. **The Universal Monolith Pattern** [Chosen]: Merge all package dependencies into the core required block. To prevent installation blocks on systems without C compilers (such as light Docker containers), write robust pure-Python fallbacks for all quantitative calculations, bypassing compile-heavy C extensions (like `ta-lib` or `quantlib`).

---

## Architectural Decisions

- **Full Dependency Integration**: All required libraries (`yfinance`, `numpy`, `pandas`, `pygithub`, `whodap`, `feedparser`, `todoist-api-python`, `jinja2`, etc.) are declared directly under the `dependencies` block of `pyproject.toml`.
- **Pure-Python Financial Fallbacks**: If standard financial indicators or quantitative scoring metrics are invoked, they execute using vectorized pure-Python/pandas calculations, completely removing system-level C binary dependencies.

---

## Implications & Consequences

- **Zero-Config Usability**: Downstream multi-agent projects can install `crewai-custom-tools` once and immediately import and execute any of the 30+ consolidated tools with zero dependency errors.
- **Pristine Installations**: Eliminates dependency extras brackets completely from downstream `pyproject.toml` files, keeping package dependency definitions clean and direct.
