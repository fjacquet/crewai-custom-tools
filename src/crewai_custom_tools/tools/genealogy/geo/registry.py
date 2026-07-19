"""Country-routed resolver chain + action/confidence decision (dataset-agnostic)."""

from __future__ import annotations

from crewai_custom_tools.tools.genealogy.geo.france import resolve_fr
from crewai_custom_tools.tools.genealogy.geo.nominatim import resolve_world
from crewai_custom_tools.tools.genealogy.geo.suisse import resolve_ch
from crewai_custom_tools.tools.genealogy.geo.transitions import apply_transition, load_transitions
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace, ResolvedPlace

# Résolveurs autoritaires par pays. Ajouter un pays = une ligne (générique).
_BY_COUNTRY = {
    "France": lambda p: resolve_fr(p),
    "Suisse": lambda p: resolve_ch(p),
}


def resolve_place(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Route to the country resolver; fall back to worldwide; apply temporal transitions."""
    country_resolver = _BY_COUNTRY.get(parsed.country)
    resolved = country_resolver(parsed) if country_resolver is not None else None
    if resolved is None:
        resolved = resolve_world(parsed)
    return apply_transition(resolved, parsed, load_transitions())


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
