"""Email Intelligence OSINT Tools."""

import logging
import os
import re

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models import (
    EpieosLookupInput,
    HoleheScanInput,
    HunterIOInput,
)

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class HunterIOTool(BaseTool):
    """A tool to search for professional email addresses related to a domain via Hunter.io API."""

    name: str = "hunter_io_search"
    description: str = (
        "Find professional email addresses for a given domain using Hunter.io."
    )
    args_schema: type[BaseModel] = HunterIOInput

    @api_tool(provider="HunterIO", endpoint="DomainSearch")
    def _run(self, domain: str) -> str:
        """Search for emails via Hunter.io REST endpoint."""
        api_key = os.getenv("HUNTER_API_KEY")
        if not api_key:
            return err("HUNTER_API_KEY environment variable not configured")

        url = "https://api.hunter.io/v2/domain-search"
        params = {"domain": domain, "api_key": api_key}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return ok(response.json().get("data", {}))


class SerperEmailSearchInput(BaseModel):
    """Input schema for Serper email search."""

    query: str = Field(
        ..., description="The name of the company or topic to scan for emails."
    )


class SerperEmailSearchTool(BaseTool):
    """A tool to scrape public emails mentioned on Google using Serper API."""

    name: str = "serper_email_search"
    description: str = "Search Google organic listings for publicly mentioned email addresses related to a company name."
    args_schema: type[BaseModel] = SerperEmailSearchInput

    @api_tool(provider="Serper", endpoint="EmailSearch")
    def _run(self, query: str) -> str:
        """Execute web query search and parse email addresses."""
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return err("SERPER_API_KEY environment variable not set.")

        clean_query = query.strip().lower()
        # Balanced quotes: the domain-guess must sit INSIDE the quotes.
        search_query = f'"{clean_query}" "@{clean_query.replace(" ", "")}" email'

        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": search_query},
            timeout=10,
        )
        response.raise_for_status()

        emails_found = set()
        for item in response.json().get("organic", []):
            combined = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('link', '')}"
            emails_found.update(_EMAIL_RE.findall(combined))

        return ok({"query": query, "emails": sorted(emails_found)})


class EpieosEmailLookupTool(BaseTool):
    """Reverse search an email to find linked Google/social profiles via the Epieos API."""

    name: str = "epieos_email_lookup"
    description: str = (
        "Reverse-search an email via the Epieos API to retrieve linked social media "
        "accounts, Google profiles, and reviews. Requires EPIEOS_API_KEY."
    )
    args_schema: type[BaseModel] = EpieosLookupInput

    @api_tool(provider="Epieos", endpoint="ReverseLookup")
    def _run(self, email: str) -> str:
        """Query the official Epieos API (keyless scraping is not reliable)."""
        api_key = os.getenv("EPIEOS_API_KEY")
        if not api_key:
            # The keyless path scraped a JS-rendered SPA and always returned empty
            # results while reporting success — worse than an honest "unavailable".
            return err("Epieos keyless lookup unavailable; set EPIEOS_API_KEY")

        response = requests.get(
            "https://api.epieos.com/v1/reverse-lookup",
            params={"email": email, "key": api_key},
            timeout=15,
        )
        response.raise_for_status()
        return ok(response.json())


class HoleheEmailScannerTool(BaseTool):
    """Check where an email is registered across 150+ popular websites in-process."""

    name: str = "holehe_email_platform_scanner"
    description: str = (
        "Scan an email address across 150+ sites (GitHub, Reddit, Twitter, Netflix) "
        "to check where it has been registered."
    )
    args_schema: type[BaseModel] = HoleheScanInput

    @api_tool(provider="Holehe", endpoint="ScanEmail")
    def _run(self, email: str) -> str:
        """Scan email across 150+ sites using the native in-process trio loop."""
        import trio

        async def run_scan():
            import httpx
            from holehe import core

            class DummyArgs:
                onlyused = False
                nocolor = True
                noclear = True
                nopasswordrecovery = False
                csvoutput = False
                timeout = 10

            modules = core.import_submodules("holehe.modules")
            websites = core.get_functions(modules, DummyArgs())

            client = httpx.AsyncClient(timeout=10)
            out: list = []
            try:
                async with trio.open_nursery() as nursery:
                    for website in websites:
                        nursery.start_soon(
                            core.launch_module, website, email, client, out
                        )
            finally:
                await client.aclose()
            return out

        try:
            raw_results = trio.run(run_scan)
        except Exception as e:  # noqa: BLE001 — import/exec failure is NOT "no accounts"
            logger.error(f"Holehe scan failed: {e}")
            return err(f"Holehe scan failed: {e}")

        found, undetermined = [], []
        for item in raw_results:
            exists = item.get("exists")
            row = {"name": item.get("name"), "exists": exists}
            if exists is True:
                found.append(row)
            elif exists is None:
                # holehe sets exists=None on rate-limit/error — surface, don't drop.
                undetermined.append(
                    {**row, "rate_limit": item.get("rateLimit", False), "error": item.get("error", False)}
                )

        return ok(
            {"email": email, "found": found, "undetermined": undetermined, "checked": len(raw_results)}
        )
