"""Country-routed resolver chain + action/confidence decision (dataset-agnostic)."""

from __future__ import annotations

from crewai_custom_tools.tools.genealogy.geo.france import resolve_fr
from crewai_custom_tools.tools.genealogy.geo.nominatim import resolve_world
from crewai_custom_tools.tools.genealogy.geo.suisse import resolve_ch
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace, ResolvedPlace

# Résolveurs autoritaires par pays. Ajouter un pays = une ligne (générique).
_BY_COUNTRY = {
    "France": lambda p: resolve_fr(p),
    "Suisse": lambda p: resolve_ch(p),
}


def resolve_place(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Route to the country resolver; fall back to the worldwide fuzzy resolver."""
    country_resolver = _BY_COUNTRY.get(parsed.country)
    if country_resolver is not None:
        resolved = country_resolver(parsed)
        if resolved is not None:
            return resolved
    return resolve_world(parsed)


def decide_action(resolved: ResolvedPlace | None, min_score: float) -> str:
    """Map a resolution to 'ecrire' | 'proposition' | 'indecidable'."""
    if resolved is None:
        return "indecidable"
    if resolved.score >= 1.0:
        return "ecrire"
    if resolved.score >= min_score and not resolved.ambiguous:
        return "ecrire"
    return "proposition"


def confiance_of(resolved: ResolvedPlace | None) -> str:
    if resolved is None:
        return "basse"
    if resolved.score >= 1.0:
        return "haute"
    if resolved.score >= 0.90 and not resolved.ambiguous:
        return "moyenne"
    return "basse"
