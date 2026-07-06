"""Username reconnaissance and intelligence tools (Sherlock-style)."""

import json
import logging
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, List
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


class UsernameSearchInput(BaseModel):
    """Input schema for UsernameSearchTool."""

    username: str = Field(
        ...,
        description="The username to scan across social networks (e.g., 'john_doe').",
    )


class UsernameSearchTool(BaseTool):
    """A pure-Python Sherlock-style tool to scan for a username across major platforms."""

    name: str = "username_search"
    description: str = "Scans multiple major social media platforms and websites to check if a username exists."
    args_schema: type[BaseModel] = UsernameSearchInput

    @api_tool(provider="UsernameRecon", endpoint="Scan", default_return="[]")
    def _run(self, username: str) -> str:
        """Scan popular platforms for the target username directly."""
        # Sanity check
        clean_username = username.strip()
        if not clean_username or " " in clean_username:
            return json.dumps({"error": "Invalid username: cannot contain spaces."})

        # Focus platforms with stable public profile URLs
        platforms = {
            "GitHub": f"https://github.com/{clean_username}",
            "Reddit": f"https://www.reddit.com/user/{clean_username}",
            "Medium": f"https://medium.com/@{clean_username}",
            "Pinterest": f"https://www.pinterest.com/{clean_username}/",
            "SoundCloud": f"https://soundcloud.com/{clean_username}",
            "Dev.to": f"https://dev.to/{clean_username}",
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        hits = []
        for name, url in platforms.items():
            try:
                # We use a HEAD request where possible to make this super-fast and light on bandwidth
                response = requests.head(
                    url, headers=headers, allow_redirects=True, timeout=5
                )
                # If HEAD fails or returns some odd statuses, fall back to GET
                if response.status_code == 405:
                    response = requests.get(url, headers=headers, timeout=5)

                if response.status_code == 200:
                    hits.append(
                        {
                            "platform": name,
                            "url": url,
                            "username": clean_username,
                            "status": "Found",
                        }
                    )
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Error checking platform {name} for username {clean_username}: {e}"
                )
                continue

        return json.dumps(hits)
