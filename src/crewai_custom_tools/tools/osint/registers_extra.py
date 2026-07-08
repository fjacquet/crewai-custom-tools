"""Additional French company-register tools: INSEE Sirene and BODACC.

Sync `requests` rewrites of the osint_tools async httpx adapters — the endpoint
URLs, params, and field parsing are preserved; the async/infra layer is dropped.
"""

import os
import urllib.parse

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_INSEE_BASE = "https://api.insee.fr/api-sirene/3.11"
_BODACC_BASE = (
    "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/"
    "catalog/datasets/annonces-commerciales/records"
)


class SirenInput(BaseModel):
    """Input schema for a SIREN-keyed register lookup."""

    siren: str = Field(..., description="9-digit French SIREN company identifier.")


class InseeSireneTool(BaseTool):
    """Authoritative FR firmographics (NAF, workforce band, active status) from INSEE Sirene."""

    name: str = "insee_sirene_lookup"
    description: str = (
        "Look up authoritative French company firmographics by SIREN from the INSEE "
        "Sirene register: legal name, NAF activity code, workforce band, and active "
        "status. Requires INSEE_SIRENE_API_KEY."
    )
    args_schema: type[BaseModel] = SirenInput

    @api_tool(provider="InseeSirene", endpoint="SirenLookup")
    def _run(self, siren: str) -> str:
        """Fetch the uniteLegale record for a SIREN from INSEE Sirene V3.11."""
        api_key = os.getenv("INSEE_SIRENE_API_KEY")
        if not api_key:
            return err("INSEE_SIRENE_API_KEY not configured")

        siren = siren.strip()
        url = f"{_INSEE_BASE}/siren/{urllib.parse.quote(siren)}"
        response = requests.get(
            url, headers={"X-INSEE-Api-Key-Integration": api_key}, timeout=10
        )
        response.raise_for_status()
        payload = response.json()

        unite = payload.get("uniteLegale") or {}
        periodes = unite.get("periodesUniteLegale") or []
        latest = periodes[0] if periodes else {}
        etat = latest.get("etatAdministratifUniteLegale")

        return ok(
            {
                "siren": unite.get("siren"),
                "name": unite.get("denominationUniteLegale"),
                "naf": latest.get("activitePrincipaleUniteLegale"),
                "workforce_band": unite.get("trancheEffectifsUniteLegale"),
                "active": etat == "A" if etat is not None else None,
                "source": "insee_sirene",
            }
        )


_INSOLVENCY_HINTS = ("collective", "conciliation", "rétablissement", "sauvegarde")
_DEPOSIT_HINTS = ("dépôt", "compte")
_SALE_HINTS = ("vente", "cession")
_CREATION_HINTS = ("création", "immatriculation")


def _classify_family(label: str | None) -> str:
    """Bucket a BODACC ``familleavis_lib`` label into a coarse event family."""
    text = (label or "").casefold()
    if any(hint in text for hint in _INSOLVENCY_HINTS):
        return "insolvency"
    if any(hint in text for hint in _DEPOSIT_HINTS):
        return "deposit"
    if any(hint in text for hint in _SALE_HINTS):
        return "sale"
    if any(hint in text for hint in _CREATION_HINTS):
        return "creation"
    return "modification"


def _bodacc_event(record: dict) -> dict:
    """Map one BODACC record to a compact event dict."""
    familleavis = record.get("familleavis_lib")
    commercant = record.get("commercant") or ""
    jugement = record.get("jugement")
    nature = jugement.get("nature") if isinstance(jugement, dict) else None
    summary = " — ".join(part for part in (familleavis, commercant, nature) if part)
    return {
        "date": record.get("dateparution"),
        "family": _classify_family(familleavis),
        "kind": record.get("typeavis_lib") or familleavis,
        "summary": summary,
    }


class BodaccTool(BaseTool):
    """Keyless BODACC legal-gazette events (creation/deposit/sale/insolvency) by SIREN."""

    name: str = "bodacc_events"
    description: str = (
        "Fetch French BODACC legal-gazette trigger events for a company by SIREN — "
        "creations, account deposits, sales/transfers, insolvency proceedings and "
        "modifications, most recent first. Keyless."
    )
    args_schema: type[BaseModel] = SirenInput

    @api_tool(provider="Bodacc", endpoint="Events")
    def _run(self, siren: str) -> str:
        """Fetch BODACC trigger events for a SIREN from the Opendatasoft dataset."""
        siren = siren.strip()
        params = {
            "where": f'registre="{siren}"',
            "order_by": "dateparution desc",
            "limit": 20,
        }
        response = requests.get(_BODACC_BASE, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("results", []) if isinstance(payload, dict) else []
        return ok({"siren": siren, "events": [_bodacc_event(r) for r in records]})
