# Design Specification: OSINTFR Curated Tools Integration

**Date**: 2026-07-05
**Status**: APPROVED / MAINTAINED
**Author**: Gemini CLI & Collaborative Engineering Team

---

## 1. Executive Summary

This document specifies the design and integration of three premium, high-yield open-source intelligence (OSINT) tools sourced from the **OSINTFR.com** directory into our consolidated `crewai-custom-tools` suite:

1. **Epieos Reverse Email Lookup (`EpieosEmailLookupTool`)**: Conducts silent reverse searches on an email to retrieve linked social media accounts and Google Maps reviews.
2. **Holehe Email Platform Scanner (`HoleheEmailScannerTool`)**: Scans an email across 150+ popular websites to locate registered user profiles.
3. **OpenCorporates Global Company Search (`OpenCorporatesSearchTool`)**: Conducts global corporate registry lookups across millions of corporate filings.

All three tools are integrated natively into our **Universal Monolith (Approach A)** and support a **Hybrid API Authentication (Decision 8)**, executing keyless/scraped fallback retrievals out of the box, with automatic speed and volume upgrades when API keys are available in the environment.

---

## 2. Directory Structure and File Responsibility

The new modules are integrated directly into our clean, domain-specific directory structure:

```text
src/crewai_custom_tools/
├── models/
│   ├── __init__.py
│   └── osintfr_models.py          # Centralized Pydantic schemas for the new tools
└── tools/
    └── osint/
        ├── __init__.py            # Exports all new OSINT tools
        ├── github.py
        ├── email_recon.py         # Hunter, Serper Search + Epieos & Holehe integrations
        ├── domain_recon.py
        ├── registers.py           # French Registries (Societe.ninja equivalents)
        ├── person_recon.py        # Username checking
        └── corporate_global.py    # OpenCorporates global company search
```

---

## 3. Detailed Component Specifications

### 3.1 Pydantic Validation Schemas (`models/osint_models.py` / `models/finance_models.py`)

Every tool strictly validates its input arguments using custom Pydantic schemas:

```python
from pydantic import BaseModel, Field
from typing import Optional

class EpieosLookupInput(BaseModel):
    email: str = Field(..., description="The target email address to reverse-search (e.g., 'test@gmail.com').")

class HoleheScanInput(BaseModel):
    email: str = Field(..., description="The target email address to scan across 150+ platforms.")

class OpenCorporatesSearchInput(BaseModel):
    query: str = Field(..., description="The name of the company or registration ID to search for globally.")
    jurisdiction_code: Optional[str] = Field(None, description="Optional: 2-letter country or state code (e.g., 'us_ca', 'gb') to restrict search.")
```

---

### 3.2 Epieos Reverse Email Lookup (`EpieosEmailLookupTool`)

* **Design**: Scrapes Epieos' public JSON endpoints keylessly or calls their official developer API if `EPIEOS_API_KEY` is present.
* **Resiliency**: Wrapped with `@api_tool` to handle rate limits and request failures gracefully.
* **Output**: Returns a JSON object containing linked Google profiles, reviews list, and active social media accounts.

### 3.3 Holehe Email Platform Scanner (`HoleheEmailScannerTool`)

* **Design**: Imports the standard Python `holehe` module directly and executes local asynchronous checks across 150+ sites in a synchronous-wrapped threadpool block.
* **Resiliency**: Completely offline-friendly (requires zero API keys) but runs within a timeout boundary.
* **Output**: Returns a list of sites where the email is registered.

### 3.4 OpenCorporates Global Company Search (`OpenCorporatesSearchTool`)

* **Design**: Queries OpenCorporates' official JSON endpoint `https://api.opencorporates.com/v1/companies/search`. It runs keylessly by default, and automatically appends the `api_token` parameter if `OPENCORPORATES_API_KEY` is set.
* **Resiliency**: Respects rate limits, and uses the TTL cache to prevent duplicate queries on identical business targets.
* **Output**: Returns structured company registration details, status, addresses, and official filing links.

---

## 4. Testing and Mock Verification

* **Mock-based Tests**: All tests are written using `pytest` and `pytest-mock` to guarantee offline stability (no real network requests to Epieos, OpenCorporates, or Holehe's servers).
* **Edge Case Simulation**: Tests explicitly simulate rate limit responses and invalid email formats to ensure unhandled exceptions never crash agent loops.
