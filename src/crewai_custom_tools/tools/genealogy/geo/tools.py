"""Agent-facing place resolution tool over the country-routed geo engine.

One BaseTool exposing parse_pname + registry.resolve_place/decide_action: raw place
string in, resolved hierarchy + GPS + score + action out. Read-only (the geocoding
APIs it calls — geo.api.gouv.fr, swisstopo, BKG dataset, Census, Nominatim — are free).
"""

import logging

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok
from crewai_custom_tools.tools.genealogy.geo.registry import (
    confiance_of,
    decide_action,
    resolve_place,
)
from crewai_custom_tools.tools.genealogy.standardize.places import parse_pname

logger = logging.getLogger(__name__)


class GenealogyResolvePlaceInput(BaseModel):
    """Input schema for GenealogyResolvePlaceTool."""

    raw: str = Field(..., description='Raw place string, e.g. "Bourges, Cher, France".')
    min_score: float = Field(0.90, description="Score threshold for action=ecrire.")


class GenealogyResolvePlaceTool(BaseTool):
    """Resolve one raw place string against the country-routed geocoding engine."""

    name: str = "genealogy_resolve_place"
    description: str = (
        "Resolves a raw place string (France/Suisse/Allemagne/USA + worldwide fallback) "
        "into a normalized hierarchy with WGS84 GPS, a confidence score, the source "
        "used, and the recommended action (ecrire/proposition/indecidable). Read-only."
    )
    args_schema: type[BaseModel] = GenealogyResolvePlaceInput

    @api_tool(provider="GeoRegistry", endpoint="ResolvePlace", timeout=30.0)
    def _run(self, raw: str, min_score: float = 0.90) -> str:
        parsed = parse_pname(raw)
        resolved = resolve_place(parsed)
        result = {
            "query": raw,
            "pays": parsed.country,
            "commune": parsed.commune,
            "action": decide_action(resolved, min_score),
            "confiance": confiance_of(resolved, min_score),
            "resolved": resolved.model_dump() if resolved else None,
        }
        return ok(result)
