"""Username reconnaissance and intelligence tools (Sherlock-style)."""

import concurrent.futures
import logging

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Per-site rules. `url` is the profile URL template; `absent_markers` are
# case-insensitive substrings that appear on a "no such profile" page returned
# with HTTP 200 (soft-404), letting us reject login-wall/soft-404 false positives.
_PLATFORMS = {
    "GitHub": {"url": "https://github.com/{u}", "absent_markers": []},
    "Reddit": {
        "url": "https://www.reddit.com/user/{u}/",
        "absent_markers": ["nobody on reddit goes by that name", "this account has been suspended"],
    },
    "Medium": {
        "url": "https://medium.com/@{u}",
        "absent_markers": ["page not found", "out of nowhere"],
    },
    "Pinterest": {
        "url": "https://www.pinterest.com/{u}/",
        "absent_markers": ["couldn't find", "user not found"],
    },
    "SoundCloud": {"url": "https://soundcloud.com/{u}", "absent_markers": []},
    "Dev.to": {"url": "https://dev.to/{u}", "absent_markers": []},
}


def _classify(name: str, cfg: dict, username: str) -> tuple[str, str, str]:
    """Check one platform and classify as found / not_found / unknown.

    A 404 means absent; a 200 without an "absent" body marker means present;
    a block/rate-limit (403/429/5xx) or a transport error means *unknown* — we
    could not tell, which is deliberately distinct from "not found".
    """
    url = cfg["url"].format(u=username)
    headers = {"User-Agent": _USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=5)
    except requests.exceptions.RequestException:
        return (name, url, "unknown")

    status = resp.status_code
    if status == 404:
        return (name, url, "not_found")
    if status in (403, 429) or status >= 500:
        return (name, url, "unknown")
    if status == 200:
        body = (resp.text or "").lower()
        if any(marker in body for marker in cfg["absent_markers"]):
            return (name, url, "not_found")
        return (name, url, "found")
    return (name, url, "unknown")


class UsernameSearchInput(BaseModel):
    """Input schema for UsernameSearchTool."""

    username: str = Field(
        ...,
        description="The username to scan across social networks (e.g., 'john_doe').",
    )


class UsernameSearchTool(BaseTool):
    """A pure-Python tool that checks whether a username exists across major platforms."""

    name: str = "username_search"
    description: str = (
        "Checks major social platforms for a username. Reports profiles found, and "
        "separately reports platforms that could not be determined (blocked/rate-limited)."
    )
    args_schema: type[BaseModel] = UsernameSearchInput

    @api_tool(provider="UsernameRecon", endpoint="Scan")
    def _run(self, username: str) -> str:
        """Scan popular platforms for the target username, concurrently."""
        clean_username = username.strip()
        if not clean_username or " " in clean_username:
            return err("Invalid username: cannot contain spaces.")

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(_PLATFORMS)
        ) as executor:
            verdicts = list(
                executor.map(
                    lambda item: _classify(item[0], item[1], clean_username),
                    _PLATFORMS.items(),
                )
            )

        found = [
            {"platform": name, "url": url}
            for name, url, verdict in verdicts
            if verdict == "found"
        ]
        unknown = [
            {"platform": name, "url": url}
            for name, url, verdict in verdicts
            if verdict == "unknown"
        ]
        return ok(
            {
                "username": clean_username,
                "found": found,
                "unknown": unknown,
                "checked": len(verdicts),
            }
        )
