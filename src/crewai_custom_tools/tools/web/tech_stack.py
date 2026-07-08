"""Website technology-stack detection via Serper search of tech-profiling sites."""

import os
import re

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

# Technology keywords grouped by category; matched (word-boundary) against search snippets.
_TECH_PATTERNS: dict[str, list[str]] = {
    "frameworks": [
        "react", "angular", "vue", "next.js", "nuxt.js", "gatsby", "svelte",
        "django", "flask", "laravel", "ruby on rails", "express", "spring", "asp.net",
    ],
    "cms": [
        "wordpress", "drupal", "joomla", "wix", "squarespace", "shopify",
        "webflow", "ghost", "contentful", "strapi", "sanity",
    ],
    "analytics": [
        "google analytics", "google tag manager", "matomo", "hotjar",
        "mixpanel", "amplitude", "segment", "heap",
    ],
    "hosting": [
        "aws", "google cloud", "azure", "cloudflare", "vercel", "netlify",
        "heroku", "digitalocean", "linode", "vultr",
    ],
}


class TechStackInput(BaseModel):
    """Input schema for tech-stack analysis."""

    domain: str = Field(..., description="Domain name to analyze, e.g. 'example.com'.")
    detailed: bool = Field(False, description="Also return a per-category breakdown.")


class TechStackTool(BaseTool):
    """Detect a website's technology stack by searching tech-profiling sites (requires SERPER_API_KEY)."""

    name: str = "tech_stack_analysis"
    description: str = (
        "Analyze the technology stack of a website by searching BuiltWith/Wappalyzer/StackShare "
        "and extracting known frameworks, CMS, analytics, and hosting providers."
    )
    args_schema: type[BaseModel] = TechStackInput

    @api_tool(provider="Serper", endpoint="TechStack")
    def _run(self, domain: str, detailed: bool = False) -> str:
        """Search tech-profiling sites for the domain and extract detected technologies."""
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return err("SERPER_API_KEY not configured")

        query = f"site:builtwith.com OR site:wappalyzer.com OR site:stackshare.io {domain}"
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=15,
        )
        response.raise_for_status()
        organic = response.json().get("organic", [])

        found: set[str] = set()
        for item in organic:
            text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
            for patterns in _TECH_PATTERNS.values():
                for pattern in patterns:
                    if re.search(rf"\b{re.escape(pattern)}\b", text):
                        found.add(pattern)

        result: dict = {"domain": domain, "technologies": sorted(found)}
        if detailed:
            result["by_category"] = {
                category: sorted(t for t in found if t in patterns)
                for category, patterns in _TECH_PATTERNS.items()
                if any(t in patterns for t in found)
            }
        return ok(result)
