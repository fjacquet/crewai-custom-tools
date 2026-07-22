"""Web scraping tools with automatic fallback escalation."""

import json
import logging
import os
import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


def _clean_text(html: str) -> str:
    """Strip scripts/styles and collapse whitespace from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    lines = (line.strip() for line in soup.get_text(separator=" ").splitlines())
    return "\n".join(line for line in lines if line)


def _scrapeninja(url: str, api_key: str) -> dict:
    """Scrape via the ScrapeNinja proxy API. Returns the uniform scrape dict."""
    response = requests.post(
        "https://scrapeninja.p.rapidapi.com/scrape",
        headers={
            "Content-Type": "application/json",
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "scrapeninja.p.rapidapi.com",
        },
        json={"url": url, "retryNum": 1, "followRedirects": True, "timeout": 10},
        timeout=15,
    )
    response.raise_for_status()
    return {
        "provider": "scrapeninja",
        "title": None,
        "content": _clean_text(response.json().get("body", ""))[:20000],
    }


def _firecrawl(url: str, api_key: str) -> dict:
    """Scrape via the Firecrawl App (tolerant of SDK dict or object results)."""
    from firecrawl import FirecrawlApp

    data = FirecrawlApp(api_key=api_key).scrape_url(url, formats=["html"])
    if isinstance(data, dict):
        html = data.get("html", "")
    else:
        html = getattr(data, "html", "") or ""
        if not html and hasattr(data, "model_dump"):
            html = data.model_dump().get("html", "")
    return {"provider": "firecrawl", "title": None, "content": _clean_text(html)[:20000]}


class UnifiedScraperInput(BaseModel):
    """Input schema for the Unified Scraper Tool."""

    url: str = Field(..., description="The URL of the website to scrape.")
    provider: str | None = Field(
        None,
        description="Optional: force a provider: 'standard' (BeautifulSoup), 'scrapeninja', 'firecrawl'.",
    )


class UnifiedScraperTool(BaseTool):
    """A highly resilient web scraper with multi-provider fallback logic."""

    name: str = "web_scraper"
    description: str = (
        "Scrapes HTML content and text from any website URL. Automatically detects and uses "
        "ScrapeNinja or Firecrawl if standard scraping is blocked by Cloudflare or JS rendering."
    )
    args_schema: type[BaseModel] = UnifiedScraperInput

    def _scrape_standard(self, url: str) -> dict:
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
        title = soup.title.string if soup.title and soup.title.string else "No title"
        return {
            "provider": "standard",
            "title": title,
            "content": _clean_text(response.text)[:20000],
        }

    def _scrape_scrapeninja(self, url: str, api_key: str) -> dict:
        """Scrape via ScrapeNinja proxy API (delegates to the shared helper)."""
        return _scrapeninja(url, api_key)

    def _scrape_firecrawl(self, url: str, api_key: str) -> dict:
        """Scrape via the Firecrawl App (delegates to the shared helper)."""
        return _firecrawl(url, api_key)

    @api_tool(provider="UniversalScraper", endpoint="Scrape")
    def _run(self, url: str, provider: str | None = None) -> str:
        """Execute web scraping with fallback orchestration."""
        provider_env = os.getenv("WEB_SCRAPER_PROVIDER", "").strip().lower()
        selected_provider = provider.lower() if provider else provider_env

        if selected_provider == "scrapeninja":
            api_key = os.getenv("RAPIDAPI_KEY")
            if not api_key:
                return err("RAPIDAPI_KEY not set for ScrapeNinja")
            return ok(self._scrape_scrapeninja(url, api_key))

        if selected_provider == "firecrawl":
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if not api_key:
                return err("FIRECRAWL_API_KEY not set for Firecrawl")
            return ok(self._scrape_firecrawl(url, api_key))

        # Standard with auto-escalation to any provider whose key is present.
        try:
            return ok(self._scrape_standard(url))
        except Exception as e:
            logger.warning(f"Standard scraping failed for {url}: {e}. Escalating...")

        ninja_key = os.getenv("RAPIDAPI_KEY")
        if ninja_key:
            try:
                return ok(self._scrape_scrapeninja(url, ninja_key))
            except Exception as ninja_err:
                logger.error(f"Escalation to ScrapeNinja failed: {ninja_err}")

        firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
        if firecrawl_key:
            try:
                return ok(self._scrape_firecrawl(url, firecrawl_key))
            except Exception as firecrawl_err:
                logger.error(f"Escalation to Firecrawl failed: {firecrawl_err}")

        return err(f"Scrape failed across all available providers for {url}")


class _ScrapeUrlInput(BaseModel):
    """Input schema for the single-URL scraper tools."""

    url: str = Field(..., description="The URL of the website to scrape.")


class ScrapeNinjaTool(BaseTool):
    """Standalone scraper using the ScrapeNinja proxy API (handles JS/Cloudflare blocks)."""

    name: str = "scrape_ninja"
    description: str = (
        "Scrape a website via the ScrapeNinja proxy API, which bypasses many JS/Cloudflare "
        "blocks. Requires the RAPIDAPI_KEY environment variable."
    )
    args_schema: type[BaseModel] = _ScrapeUrlInput

    @api_tool(provider="ScrapeNinja", endpoint="Scrape")
    def _run(self, url: str) -> str:
        api_key = os.getenv("RAPIDAPI_KEY")
        if not api_key:
            return err("RAPIDAPI_KEY not set for ScrapeNinja")
        return ok(_scrapeninja(url, api_key))


class FirecrawlTool(BaseTool):
    """Standalone scraper using the Firecrawl API."""

    name: str = "firecrawl_scraper"
    description: str = (
        "Scrape a website via the Firecrawl API. Requires the FIRECRAWL_API_KEY environment "
        "variable and the optional 'firecrawl' SDK."
    )
    args_schema: type[BaseModel] = _ScrapeUrlInput

    @api_tool(provider="Firecrawl", endpoint="Scrape")
    def _run(self, url: str) -> str:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            return err("FIRECRAWL_API_KEY not set for Firecrawl")
        try:
            return ok(_firecrawl(url, api_key))
        except ImportError:
            return err("firecrawl SDK not installed")


class BatchArticleScraperInput(BaseModel):
    """Input schema for the batch article scraper."""

    urls: list[str] = Field(..., description="List of article URLs to scrape.")


class BatchArticleScraperTool(BaseTool):
    """Scrape many article URLs, returning extracted text for each via the unified scraper."""

    name: str = "batch_article_scraper"
    description: str = (
        "Scrape a batch of article URLs and return the extracted text content for each, using "
        "the resilient unified scraper with automatic provider fallback."
    )
    args_schema: type[BaseModel] = BatchArticleScraperInput

    @api_tool(provider="BatchScraper", endpoint="Scrape")
    def _run(self, urls: list[str]) -> str:
        scraper = UnifiedScraperTool()
        articles = []
        for url in urls:
            payload = json.loads(scraper._run(url=url))
            if payload.get("success"):
                data = payload.get("data") or {}
                articles.append(
                    {"url": url, "title": data.get("title"), "content": data.get("content")}
                )
            else:
                articles.append({"url": url, "error": payload.get("error")})
        return ok({"count": len(articles), "articles": articles})
