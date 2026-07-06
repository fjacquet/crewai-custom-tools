# OSINTFR Tools Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Epieos Reverse Email Lookup, Holehe Platform Scanner, and OpenCorporates Global Company Search natively into our consolidated `crewai-custom-tools` Universal Monolith library.

**Architecture:** Add Pydantic schemas, write modular REST client wrappers using `@api_tool` and `@cache_api_call` decorators, utilize the python `holehe` library directly for platform checks, and expose everything in our main root package space.

**Tech Stack:** Python 3.11+, `pytest>=8.0.0` (TDD / Mock-based tests), `holehe`, `requests`, `pydantic>=2.0.0`, `beautifulsoup4`.

## Global Constraints

- **Universal Monolith Pattern**: All requirements are added directly into core dependencies of `pyproject.toml`.
- **SHA-256 Keying**: Standardize on `hashlib.sha256` digests truncated to 32 characters for cached filenames.
- **Clean Namespace Exports**: Expose all new public tools inside the package root `__init__.py` and the respective sub-package files for simple importing.
- **Strict pytest Rule**: All tests must use `pytest` with mock structures. Absolutely no `unittest` class patterns allowed.

---

### Task 1: Setup Dependencies and Centralized Schemas

**Files:**

- Modify: `pyproject.toml`
- Create: `src/crewai_custom_tools/models/osintfr_models.py`
- Modify: `src/crewai_custom_tools/models/__init__.py`

**Interfaces:**

- Consumes: None
- Produces: `osintfr` validation models (`EpieosLookupInput`, `HoleheScanInput`, `OpenCorporatesSearchInput`) and updated dependencies.

- [ ] **Step 1: Write complete dependencies in pyproject.toml**

Add `holehe>=2.0.0` to pyproject.toml:

```toml
dependencies = [
    # ... other core dependencies
    "holehe>=2.0.0",
]
```

- [ ] **Step 2: Create centralized Pydantic models**

Create `src/crewai_custom_tools/models/osintfr_models.py`:

```python
"""Pydantic models for OSINTFR curated tools."""

from pydantic import BaseModel, Field
from typing import Optional


class EpieosLookupInput(BaseModel):
    """Input schema for EpieosEmailLookupTool."""
    email: str = Field(..., description="The target email address to reverse-search (e.g., 'test@gmail.com').")


class HoleheScanInput(BaseModel):
    """Input schema for HoleheEmailScannerTool."""
    email: str = Field(..., description="The target email address to scan across 150+ platforms.")


class OpenCorporatesSearchInput(BaseModel):
    """Input schema for OpenCorporatesSearchTool."""
    query: str = Field(..., description="The name of the company or registration ID to search for globally.")
    jurisdiction_code: Optional[str] = Field(None, description="Optional: 2-letter country or state code (e.g., 'us_ca', 'gb') to restrict search.")
```

- [ ] **Step 3: Update models root package exports**

Modify `src/crewai_custom_tools/models/__init__.py` to export everything:

```python
from crewai_custom_tools.models.osintfr_models import *
```

- [ ] **Step 4: Install package and verify dependencies**

Run editable installation:

```bash
rtk proxy uv pip install -e ".[dev]"
```

Expected: Package compiles and installs cleanly.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/crewai_custom_tools/models/
git commit -m "chore: add holehe dependencies and configure centralized OSINTFR schemas"
```

---

### Task 2: Implement Epieos & Holehe Email Tools

We will integrate `EpieosEmailLookupTool` and `HoleheEmailScannerTool` directly into our existing `email_recon.py` module.

**Files:**

- Modify: `src/crewai_custom_tools/tools/osint/email_recon.py`
- Modify: `src/crewai_custom_tools/tools/osint/__init__.py`
- Modify: `tests/test_osint_tools.py`

**Interfaces:**

- Consumes: `EpieosLookupInput` and `HoleheScanInput`.
- Produces: `EpieosEmailLookupTool` and `HoleheEmailScannerTool` under `crewai_custom_tools.tools.osint`.

- [ ] **Step 1: Update email_recon.py with Epieos and Holehe**

Expose both tools at the end of `src/crewai_custom_tools/tools/osint/email_recon.py`:

- `EpieosEmailLookupTool`: queries `https://api.epieos.com/v1/reverse-lookup` or runs standard scraped JSON fallback if key is missing.
- `HoleheEmailScannerTool`: imports `holehe` locally, executes its checking engine on 150+ sites, and returns a JSON list of matches.

- [ ] **Step 2: Update subpackage exports**

Expose tools in `src/crewai_custom_tools/tools/osint/__init__.py`:

```python
from crewai_custom_tools.tools.osint.email_recon import EpieosEmailLookupTool, HoleheEmailScannerTool
```

- [ ] **Step 3: Write mock-based tests in tests/test_osint_tools.py**

Write:

- `test_epieos_email_lookup_success` mocking requests success.
- `test_holehe_email_scanner_success` mocking the `holehe` async library call.

- [ ] **Step 4: Run unit tests**

```bash
rtk proxy uv run python -m pytest tests/test_osint_tools.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crewai_custom_tools/tools/osint/email_recon.py src/crewai_custom_tools/tools/osint/__init__.py tests/test_osint_tools.py
git commit -m "feat: implement Epieos lookup and Holehe email platform scanner tools and tests"
```

---

### Task 3: Implement OpenCorporates Global Company Search

We will create `src/crewai_custom_tools/tools/osint/corporate_global.py` containing `OpenCorporatesSearchTool`.

**Files:**

- Create: `src/crewai_custom_tools/tools/osint/corporate_global.py`
- Modify: `src/crewai_custom_tools/tools/osint/__init__.py`
- Modify: `tests/test_osint_tools.py`

**Interfaces:**

- Consumes: `OpenCorporatesSearchInput`.
- Produces: `OpenCorporatesSearchTool` under `crewai_custom_tools.tools.osint`.

- [ ] **Step 1: Create corporate_global.py**

Create `src/crewai_custom_tools/tools/osint/corporate_global.py` querying OpenCorporates API `https://api.opencorporates.com/v1/companies/search` using hybrid key authorization.

- [ ] **Step 2: Update subpackage exports**

Expose in `src/crewai_custom_tools/tools/osint/__init__.py`:

```python
from crewai_custom_tools.tools.osint.corporate_global import OpenCorporatesSearchTool
```

- [ ] **Step 3: Write mock tests in tests/test_osint_tools.py**

Write `test_opencorporates_search_success` mocking OpenCorporates payload details.

- [ ] **Step 4: Run unit tests**

```bash
rtk proxy uv run python -m pytest tests/test_osint_tools.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crewai_custom_tools/tools/osint/corporate_global.py src/crewai_custom_tools/tools/osint/__init__.py tests/test_osint_tools.py
git commit -m "feat: implement OpenCorporates global corporate search tool and tests"
```

---

### Task 4: Main Public API Exports & Verification

**Files:**

- Modify: `src/crewai_custom_tools/__init__.py`
- Modify: `tests/test_exports.py`

**Interfaces:**

- Consumes: New tools.
- Produces: Complete root package-level exports.

- [ ] **Step 1: Export tools at root level**

Update `src/crewai_custom_tools/__init__.py` to include `EpieosEmailLookupTool`, `HoleheEmailScannerTool`, and `OpenCorporatesSearchTool` inside `__all__`.

- [ ] **Step 2: Update exports tests**

Modify `tests/test_exports.py` to assert that all three tools can be imported cleanly from the root package.

- [ ] **Step 3: Run full test suite and build docs**

Verify full package health:

```bash
rtk proxy uv run python -m pytest
uv run mkdocs build
```

Expected: 100% tests PASS and MkDocs builds successfully with zero warnings.

- [ ] **Step 4: Commit**

```bash
git add src/crewai_custom_tools/__init__.py tests/test_exports.py
git commit -m "feat: expose Epieos, Holehe, and OpenCorporates at package root and final verification"
```
