"""Hunter.io email-finder and email-verifier tools.

Complements the domain-search-only HunterIOTool with the other two read-only
Hunter.io v2 endpoints. Sync `requests` rewrites of the osint_tools adapter.
"""

import os

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_HUNTER_BASE = "https://api.hunter.io/v2"


class HunterEmailFinderInput(BaseModel):
    """Input schema for Hunter.io email-finder."""

    first_name: str = Field(..., description="Person's first name.")
    last_name: str = Field(..., description="Person's last name.")
    domain: str = Field(..., description="Company domain (e.g. 'stripe.com').")


class HunterEmailFinderTool(BaseTool):
    """Guess a specific person's professional email at a company domain via Hunter.io."""

    name: str = "hunter_email_finder"
    description: str = (
        "Find the most likely professional email address for a named person at a "
        "company domain using Hunter.io. Requires HUNTER_API_KEY."
    )
    args_schema: type[BaseModel] = HunterEmailFinderInput

    @api_tool(provider="HunterIO", endpoint="EmailFinder")
    def _run(self, first_name: str, last_name: str, domain: str) -> str:
        """Look up a person's email at a domain via Hunter.io email-finder."""
        api_key = os.getenv("HUNTER_API_KEY")
        if not api_key:
            return err("HUNTER_API_KEY environment variable not configured")

        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": api_key,
        }
        response = requests.get(f"{_HUNTER_BASE}/email-finder", params=params, timeout=10)
        response.raise_for_status()
        return ok(response.json().get("data", {}))


class HunterEmailVerifierInput(BaseModel):
    """Input schema for Hunter.io email-verifier."""

    email: str = Field(..., description="Email address to verify.")


class HunterEmailVerifierTool(BaseTool):
    """Check the deliverability/status of a known email address via Hunter.io."""

    name: str = "hunter_email_verifier"
    description: str = (
        "Verify the deliverability and status (valid/invalid/accept_all/webmail/"
        "disposable/unknown) of a known email address using Hunter.io. "
        "Requires HUNTER_API_KEY."
    )
    args_schema: type[BaseModel] = HunterEmailVerifierInput

    @api_tool(provider="HunterIO", endpoint="EmailVerifier")
    def _run(self, email: str) -> str:
        """Verify an email address via Hunter.io email-verifier."""
        api_key = os.getenv("HUNTER_API_KEY")
        if not api_key:
            return err("HUNTER_API_KEY environment variable not configured")

        params = {"email": email, "api_key": api_key}
        response = requests.get(
            f"{_HUNTER_BASE}/email-verifier", params=params, timeout=10
        )
        response.raise_for_status()
        return ok(response.json().get("data", {}))
