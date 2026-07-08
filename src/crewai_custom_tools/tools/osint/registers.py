"""French Corporate Registries reconnaissance tools."""

import logging
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


class RegistrySearchInput(BaseModel):
    """Input schema for FrenchRegistryTool."""

    query: str = Field(
        ...,
        description="A SIREN (9-digit number) or free-text company name to search in the public French register.",
    )


class FrenchRegistryTool(BaseTool):
    """A tool to search the official, keyless public French corporate register (recherche-entreprises)."""

    name: str = "french_corporate_registry_search"
    description: str = "Searches the official French corporate register for company metadata, SIREN, address, status, and corporate officers."
    args_schema: type[BaseModel] = RegistrySearchInput

    @api_tool(provider="RechercheEntreprises", endpoint="Search")
    def _run(self, query: str) -> str:
        """Fetch company metadata from the public French api.gouv.fr register."""
        url = "https://recherche-entreprises.api.gouv.fr/search"
        headers = {
            "User-Agent": "crewai-custom-tools/0.1.0 (Enterprise Multi-Agent OSINT)"
        }

        response = requests.get(url, params={"q": query}, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()

        results = payload.get("results") or []
        if not results:
            return err(f"No French corporate registry results found for query: {query}")

        # Match and format the top result
        result = results[0]
        siege = result.get("siege") or {}
        complements = result.get("complements") or {}

        # Parse address fields neatly into a single line
        addr_parts = [
            siege.get("numero_voie"),
            siege.get("type_voie"),
            siege.get("libelle_voie"),
            siege.get("code_postal"),
            siege.get("libelle_commune"),
        ]
        address = " ".join(str(part) for part in addr_parts if part) or None

        # Gather officers (dirigeants). Corporate officers (personne morale) carry a
        # `denomination` instead of prenoms/nom — include them rather than dropping.
        officers = []
        for d in result.get("dirigeants") or []:
            name = f"{d.get('prenoms', '')} {d.get('nom', '')}".strip()
            if not name:
                name = (d.get("denomination") or "").strip()
            if name:
                officers.append(name)

        company_info = {
            "siren": result.get("siren"),
            "company_name": result.get("nom_complet"),
            "siret_headquarters": siege.get("siret"),
            "naf_activity_code": result.get("activite_principale"),
            "workforce_band": result.get("tranche_effectif_salarie"),
            "address": address,
            "active": result.get("etat_administratif") == "A",
            "officers": officers[:10],  # Limit to top 10 officers
            "website": complements.get("site_web"),
            "source": "French official recherche-entreprises register (DINUM)",
        }
        return ok(company_info)
