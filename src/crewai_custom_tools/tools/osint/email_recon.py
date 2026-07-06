"""Email Intelligence OSINT Tools."""

import json
import logging
import os
import re
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.models import (
    HunterIOInput,
    EpieosLookupInput,
    HoleheScanInput,
)

logger = logging.getLogger(__name__)


class HunterIOTool(BaseTool):
    """A tool to search for professional email addresses related to a domain via Hunter.io API."""

    name: str = "hunter_io_search"
    description: str = (
        "Find professional email addresses for a given domain using Hunter.io."
    )
    args_schema: type[BaseModel] = HunterIOInput

    @api_tool(provider="HunterIO", endpoint="DomainSearch", default_return="{}")
    def _run(self, domain: str) -> str:
        """Search for emails via Hunter.io REST endpoint."""
        api_key = os.getenv("HUNTER_API_KEY")
        if not api_key:
            return json.dumps(
                {"error": "HUNTER_API_KEY environment variable not configured"}
            )

        url = "https://api.hunter.io/v2/domain-search"
        params = {"domain": domain, "api_key": api_key}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return json.dumps(data.get("data", {}))


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

    @api_tool(provider="Serper", endpoint="EmailSearch", default_return="[]")
    def _run(self, query: str) -> str:
        """Execute web query search and parse email addresses."""
        api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPER_API_KEY")
        if not api_key:
            return json.dumps({"error": "SERPER_API_KEY environment variable not set."})

        # Clean query and formulate search string for email listings
        clean_query = query.strip().lower()
        search_query = f'"{clean_query}" "@"{clean_query.replace(" ", "")} email'

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": search_query}

        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        results = response.json().get("organic", [])
        emails_found = set()
        email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

        for item in results:
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            link = item.get("link", "")
            combined_text = f"{title} {snippet} {link}"
            emails_found.update(email_regex.findall(combined_text))

        result_list = list(emails_found)
        if result_list:
            return json.dumps([{"emails": result_list}])
        return json.dumps([{"message": "No emails found"}])


class EpieosEmailLookupTool(BaseTool):
    """Reverse search an email to find linked Google/social profiles and reviews via Epieos."""

    name: str = "epieos_email_lookup"
    description: str = (
        "Silent reverse-search on an email to retrieve linked social media accounts, "
        "Google profiles, avatars, and user reviews via Epieos."
    )
    args_schema: type[BaseModel] = EpieosLookupInput

    @api_tool(provider="Epieos", endpoint="ReverseLookup", default_return="{}")
    def _run(self, email: str) -> str:
        """Query Epieos API with keyless web scraping fallback."""
        api_key = os.getenv("EPIEOS_API_KEY")

        # 1. Official API Path
        if api_key:
            url = (
                f"https://api.epieos.com/v1/reverse-lookup?email={email}&key={api_key}"
            )
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return json.dumps(response.json())

        # 2. Keyless/Scraped Fallback Path
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        url = f"https://epieos.com/?q={email}"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(
                domain in href
                for domain in [
                    "google.com",
                    "maps",
                    "youtube",
                    "twitter",
                    "facebook",
                    "linkedin",
                ]
            ):
                links.append(href)

        result = {
            "email": email,
            "success": True,
            "provider": "keyless_fallback",
            "associated_profiles": list(set(links))[:10],
            "message": "Keyless fallback run. For full Epieos JSON metadata, please configure EPIEOS_API_KEY.",
        }
        return json.dumps(result)


class HoleheEmailScannerTool(BaseTool):
    """Check where an email is registered across 150+ popular websites in-process."""

    name: str = "holehe_email_platform_scanner"
    description: str = (
        "Scan an email address across 150+ sites (GitHub, Reddit, Twitter, Netflix) "
        "to check where it has been registered."
    )
    args_schema: type[BaseModel] = HoleheScanInput

    @api_tool(provider="Holehe", endpoint="ScanEmail", default_return="[]")
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

            args = DummyArgs()
            modules = core.import_submodules("holehe.modules")
            websites = core.get_functions(modules, args)

            client = httpx.AsyncClient(timeout=10)
            out = []
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
            hits = [
                {
                    "name": item.get("name"),
                    "exists": item.get("exists", False),
                    "rate_limit": item.get("rateLimit", False),
                    "error": item.get("error", False),
                }
                for item in raw_results
                if item.get("exists") is True
            ]
            return json.dumps(hits)
        except Exception as e:
            logger.error(f"Holehe scan error: {e}")
            return json.dumps([])
