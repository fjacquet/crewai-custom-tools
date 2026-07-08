"""GitHub OSINT tools for searching repos and orgs."""

import logging
import os

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


# Standard schemas
class GitHubSearchInput(BaseModel):
    """Input schema for GitHub search."""

    query: str = Field(..., description="Search query for GitHub")
    search_type: str = Field(
        default="repositories",
        description="Type of search: 'repositories', 'code', 'issues', or 'users'",
    )
    max_results: int = Field(
        default=5, description="Maximum number of results to return", ge=1, le=10
    )


class GitHubOrgSearchInput(BaseModel):
    """Input schema for GitHub organization search."""

    org_name: str = Field(
        ..., description="Name of the GitHub organization to search for"
    )


def _project(search_type: str, r: dict) -> dict:
    """Project a raw GitHub search item defensively (missing keys never nuke the set)."""
    if search_type == "repositories":
        return {
            "name": r.get("full_name"),
            "url": r.get("html_url"),
            "description": r.get("description", ""),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
        }
    if search_type == "code":
        return {
            "name": r.get("name"),
            "path": r.get("path"),
            "repository": (r.get("repository") or {}).get("full_name"),
            "url": r.get("html_url"),
        }
    if search_type == "issues":
        return {
            "title": r.get("title"),
            "url": r.get("html_url"),
            "state": r.get("state"),
            "comments": r.get("comments"),
            "created_at": r.get("created_at"),
        }
    return {  # users
        "login": r.get("login"),
        "url": r.get("html_url"),
        "type": r.get("type"),
        "score": r.get("score"),
    }


class GitHubSearchTool(BaseTool):
    """A tool to search GitHub for repositories, code, issues, or users."""

    name: str = "github_search"
    description: str = "Search GitHub for repositories, code, issues, or users."
    args_schema: type[BaseModel] = GitHubSearchInput

    @api_tool(provider="GitHub", endpoint="Search")
    def _run(
        self, query: str, search_type: str = "repositories", max_results: int = 5
    ) -> str:
        """Search GitHub."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return err("GITHUB_TOKEN environment variable not set")

        search_type = search_type.lower()
        if search_type not in ("repositories", "code", "issues", "users"):
            return err("Invalid search type. Must be: repositories, code, issues, users")

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"https://api.github.com/search/{search_type}"
        params = {"q": query, "per_page": min(max_results, 10)}

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return ok(
            {
                "search_type": search_type,
                "total_count": data.get("total_count", 0),
                "results": [_project(search_type, r) for r in data.get("items", [])],
            }
        )


class GitHubOrgSearchTool(BaseTool):
    """A tool to search GitHub organizations and extract profile metadata."""

    name: str = "github_org_search"
    description: str = (
        "Search for a GitHub organization and retrieve basic profile information."
    )
    args_schema: type[BaseModel] = GitHubOrgSearchInput

    @api_tool(provider="GitHub", endpoint="OrgSearch")
    def _run(self, org_name: str) -> str:
        """Search GitHub organizations."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return err("GITHUB_TOKEN environment variable not set")

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.get(
            f"https://api.github.com/orgs/{org_name}", headers=headers, timeout=10
        )
        if response.status_code == 404:
            return ok({"exists": False, "org": org_name})
        response.raise_for_status()
        org_data = response.json()

        # Fetch repositories and rank by stars (the org repos API can't sort by stars).
        repos = []
        repos_url = org_data.get("repos_url")
        if repos_url:
            repos_response = requests.get(repos_url, headers=headers, timeout=10)
            if repos_response.status_code == 200:
                repos = sorted(
                    (
                        {
                            "name": r.get("name"),
                            "url": r.get("html_url"),
                            "stars": r.get("stargazers_count", 0),
                        }
                        for r in repos_response.json()
                    ),
                    key=lambda repo: repo["stars"],
                    reverse=True,
                )

        return ok(
            {
                "exists": True,
                "name": org_data.get("name"),
                "login": org_data.get("login"),
                "url": org_data.get("html_url"),
                "description": org_data.get("description"),
                "public_repos": org_data.get("public_repos", 0),
                "followers": org_data.get("followers", 0),
                "top_repos": repos[:5],
            }
        )
