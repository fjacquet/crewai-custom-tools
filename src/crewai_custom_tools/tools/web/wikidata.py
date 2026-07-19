"""Wikidata SPARQL query tool (free public endpoint)."""

import logging

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "crewai-custom-tools/genealogy (research tool)"


class WikidataSparqlInput(BaseModel):
    """Input model for the WikidataSparqlTool."""

    query: str = Field(..., description="The SPARQL query to run against Wikidata.")
    limit: int = Field(25, description="Max result rows returned to the agent.")


class WikidataSparqlTool(BaseTool):
    """Runs a SPARQL query on the public Wikidata endpoint."""

    name: str = "wikidata_sparql"
    description: str = (
        "Runs a SPARQL query against Wikidata (query.wikidata.org) and returns the "
        "result rows flattened as {variable: value}. Free public endpoint; use LIMIT "
        "in the query and keep queries specific."
    )
    args_schema: type[BaseModel] = WikidataSparqlInput

    @api_tool(provider="Wikidata", endpoint="SPARQL", timeout=30.0)
    def _run(self, query: str, limit: int = 25) -> str:
        response = requests.get(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "json"},
            headers={"User-Agent": USER_AGENT,
                     "Accept": "application/sparql-results+json"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        bindings = payload.get("results", {}).get("bindings", [])
        rows = [
            {var: cell.get("value") for var, cell in binding.items()}
            for binding in bindings[:limit]
        ]
        return ok({
            "variables": payload.get("head", {}).get("vars", []),
            "count": len(rows),
            "truncated": len(bindings) > limit,
            "rows": rows,
        })
