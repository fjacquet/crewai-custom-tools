"""Google Fact Check API query tools."""

import logging
import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Optional
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger("crewai_custom_tools.fact_checking")


class GoogleFactCheckInput(BaseModel):
    """Input model for the GoogleFactCheckTool."""

    query: str = Field(..., description="The query to search for fact-checked claims.")
    review_publisher_site_filter: Optional[str] = Field(
        default=None,
        description="The review publisher site to filter results by, e.g. nytimes.com.",
    )
    language_code: Optional[str] = Field(
        default=None,
        description='The BCP-47 language code, such as "en-US" or "sr-Latn".',
    )
    max_age_days: Optional[int] = Field(
        default=None,
        description="The maximum age of the returned search results, in days.",
    )
    page_size: int = Field(default=10, description="The pagination size.")
    page_token: Optional[str] = Field(default=None, description="The pagination token.")


class GoogleFactCheckTool(BaseTool):
    """Tool to search for fact-checked claims using the Google Fact Check API."""

    name: str = "google_fact_check"
    description: str = (
        "Searches Google's Database for fact-checked claims on a given query."
    )
    args_schema: type[BaseModel] = GoogleFactCheckInput

    @api_tool(provider="GoogleFactCheck", endpoint="Search")
    def _run(self, query: str, **kwargs: Any) -> str:
        """Run the tool."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return err("GOOGLE_API_KEY not configured")

        params = {
            "query": query,
            "languageCode": kwargs.get("language_code"),
            "reviewPublisherSiteFilter": kwargs.get("review_publisher_site_filter"),
            "maxAgeDays": kwargs.get("max_age_days"),
            "pageSize": kwargs.get("page_size", 10),
            "pageToken": kwargs.get("page_token"),
            "key": api_key,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        response = requests.get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return ok(response.json())
