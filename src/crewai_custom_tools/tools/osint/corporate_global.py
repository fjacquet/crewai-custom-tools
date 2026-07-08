"""OpenCorporates global corporate registry search tool."""

import logging
import os
import requests
from typing import Optional
from crewai.tools import BaseTool
from pydantic import BaseModel
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models import OpenCorporatesSearchInput

logger = logging.getLogger(__name__)


class OpenCorporatesSearchTool(BaseTool):
    """Search for global companies using the OpenCorporates REST API."""

    name: str = "opencorporates_global_search"
    description: str = (
        "Search OpenCorporates' global corporate database for company status, "
        "registration details, jurisdiction codes, and official corporate registry links."
    )
    args_schema: type[BaseModel] = OpenCorporatesSearchInput

    @api_tool(provider="OpenCorporates", endpoint="CompanySearch")
    def _run(self, query: str, jurisdiction_code: Optional[str] = None) -> str:
        """Run global company registry search."""
        api_url = "https://api.opencorporates.com/v1/companies/search"
        params = {"q": query}

        if jurisdiction_code:
            params["jurisdiction_code"] = jurisdiction_code.strip().lower()

        # Hybrid Auth: Add api_token parameter if key is present
        api_token = os.getenv("OPENCORPORATES_API_KEY")
        if api_token:
            params["api_token"] = api_token

        response = requests.get(api_url, params=params, timeout=10)
        # OpenCorporates v1 search rejects anonymous calls — surface that clearly
        # instead of degrading to an empty result that looks like "no matches".
        if response.status_code in (401, 403):
            return err(
                "OpenCorporates requires OPENCORPORATES_API_KEY (anonymous v1 search is not permitted)."
            )
        response.raise_for_status()
        data = response.json()

        companies = data.get("results", {}).get("companies", [])
        if not companies:
            return err(f"No global corporate registry records found for query: {query}")

        # Format and normalize the corporate records
        formatted_companies = []
        for item in companies:
            comp = item.get("company", {})
            formatted_companies.append(
                {
                    "name": comp.get("name"),
                    "company_number": comp.get("company_number"),
                    "jurisdiction_code": comp.get("jurisdiction_code"),
                    "incorporation_date": comp.get("incorporation_date"),
                    "current_status": comp.get("current_status"),
                    "opencorporates_url": comp.get("opencorporates_url"),
                    "registry_url": comp.get("registry_url"),
                    "registered_address_in_full": comp.get(
                        "registered_address_in_full"
                    ),
                }
            )

        # Return structured corporate results
        return ok(
            {
                "query": query,
                "total_results": len(formatted_companies),
                "companies": formatted_companies[:5],  # Return top 5 matches
                "source": "OpenCorporates Global Registry",
            }
        )
