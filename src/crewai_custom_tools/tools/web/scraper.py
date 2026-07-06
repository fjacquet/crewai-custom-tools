"""Web scraping tools with automatic fallback escalation."""

import json
import logging
import os
import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Optional
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


class UnifiedScraperInput(BaseModel):
    """Input schema for the Unified Scraper Tool."""

    url: str = Field(..., description="The URL of the website to scrape.")
    provider: Optional[str] = Field(
        None,
        description="Optional: force a specific provider: 'standard' (BeautifulSoup), 'scrapeninja', 'firecrawl'.",
    )


class UnifiedScraperTool(BaseTool):
    """A highly resilient web scraper with multi-provider fallback logic."""

    name: str = "web_scraper"
    description: str = (
        "Scrapes HTML content and text from any website URL. Automatically detects and uses "
        "ScrapeNinja or Firecrawl if standard scraping is blocked by Cloudflare or JS rendering."
    )
    args_schema: type[BaseModel] = UnifiedScraperInput

    def _scrape_standard(self, url: str) -> str:
        """Standard BeautifulSoup scraping via requests."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator=" ")
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = "\n".join(chunk for chunk in chunks if chunk)

        return json.dumps(
            {
                "success": True,
                "provider": "standard",
                "title": soup.title.string if soup.title else "No title",
                "content": cleaned_text[:20000],  # Limit content length
            }
        )

    def _scrape_scrapeninja(self, url: str, api_key: str) -> str:
        """Scrape via ScrapeNinja proxy API."""
        api_url = "https://scrapeninja.p.rapidapi.com/scrape"
        headers = {
            "Content-Type": "application/json",
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "scrapeninja.p.rapidapi.com",
        }
        payload = {
            "url": url,
            "retryNum": 1,
            "followRedirects": True,
            "timeout": 10,
        }
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Format output
        body = data.get("body", "")
        soup = BeautifulSoup(body, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        cleaned_text = "\n".join(
            line.strip() for line in soup.get_text().splitlines() if line.strip()
        )

        return json.dumps(
            {
                "success": True,
                "provider": "scrapeninja",
                "content": cleaned_text[:20000],
            }
        )

    def _scrape_firecrawl(self, url: str, api_key: str) -> str:
        """Scrape via Firecrawl App."""
        try:
            from firecrawl import FirecrawlApp

            app = FirecrawlApp(api_key=api_key)
            data = app.scrape_url(url, formats=["html"])
            html_content = data.get("html", "")
            soup = BeautifulSoup(html_content, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            cleaned_text = "\n".join(
                line.strip() for line in soup.get_text().splitlines() if line.strip()
            )

            return json.dumps(
                {
                    "success": True,
                    "provider": "firecrawl",
                    "content": cleaned_text[:20000],
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": f"Firecrawl failed: {e}"})

    @api_tool(
        provider="UniversalScraper",
        endpoint="Scrape",
        default_return="Error: Scrape request failed.",
    )
    def _run(self, url: str, provider: Optional[str] = None) -> str:
        """Execute web scraping with fallback orchestration."""
        provider_env = os.getenv("WEB_SCRAPER_PROVIDER", "").strip().lower()
        selected_provider = provider.lower() if provider else provider_env

        # 1. Force ScrapeNinja
        if selected_provider == "scrapeninja":
            api_key = os.getenv("RAPIDAPI_KEY")
            if api_key:
                return self._scrape_scrapeninja(url, api_key)
            return json.dumps({"error": "RAPIDAPI_KEY not set for ScrapeNinja"})

        # 2. Force Firecrawl
        if selected_provider == "firecrawl":
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if api_key:
                return self._scrape_firecrawl(url, api_key)
            return json.dumps({"error": "FIRECRAWL_API_KEY not set for Firecrawl"})

        # 3. Standard with auto-escalation
        try:
            return self._scrape_standard(url)
        except Exception as e:
            logger.warning(f"Standard scraping failed for {url}: {e}. Escalating...")

            # Escalate to ScrapeNinja if key is present
            ninja_key = os.getenv("RAPIDAPI_KEY")
            if ninja_key:
                try:
                    return self._scrape_scrapeninja(url, ninja_key)
                except Exception as ninja_err:
                    logger.error(f"Escalation to ScrapeNinja failed: {ninja_err}")

            # Escalate to Firecrawl if key is present
            firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
            if firecrawl_key:
                try:
                    return self._scrape_firecrawl(url, firecrawl_key)
                except Exception as firecrawl_err:
                    logger.error(f"Escalation to Firecrawl failed: {firecrawl_err}")

            return json.dumps(
                {
                    "success": False,
                    "error": f"Scrape failed across all providers. Core error: {e}",
                }
            )
