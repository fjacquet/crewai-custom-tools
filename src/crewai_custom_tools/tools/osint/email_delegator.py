"""Delegating email-search tool that routes to Hunter.io or Serper (reuses our tools)."""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.results import err
from crewai_custom_tools.tools.osint.email_recon import HunterIOTool, SerperEmailSearchTool


class DelegatingEmailSearchInput(BaseModel):
    """Input schema for DelegatingEmailSearchTool."""

    provider: str = Field(
        ..., description="'hunter' for a domain search, 'serper' for a company-name/web search."
    )
    query: str = Field(..., description="A domain (for hunter) or a company/name (for serper).")


class DelegatingEmailSearchTool(BaseTool):
    """Route an email search to Hunter.io (domain) or Serper (company/web)."""

    name: str = "email_search_router"
    description: str = (
        "Find professional email addresses via a chosen provider. Use 'hunter' for a domain "
        "(e.g. 'example.com') or 'serper' for a company name / broader web search (e.g. 'Example Inc')."
    )
    args_schema: type[BaseModel] = DelegatingEmailSearchInput

    def _run(self, provider: str, query: str) -> str:
        """Delegate to the selected provider's tool; both already return the envelope."""
        provider = provider.lower().strip()
        if provider == "hunter":
            return HunterIOTool()._run(domain=query)
        if provider == "serper":
            return SerperEmailSearchTool()._run(query=query)
        return err(f"Invalid provider '{provider}'. Must be 'hunter' or 'serper'.")
