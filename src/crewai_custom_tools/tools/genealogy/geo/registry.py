"""Country-routed resolver chain + action/confidence decision (dataset-agnostic)."""

from __future__ import annotations

from crewai_custom_tools.tools.genealogy.geo.allemagne import resolve_de
from crewai_custom_tools.tools.genealogy.geo.france import resolve_fr
from crewai_custom_tools.tools.genealogy.geo.france_ex_communes import resolve_fr_ex_commune
from crewai_custom_tools.tools.genealogy.geo.nominatim import resolve_world
from crewai_custom_tools.tools.genealogy.geo.suisse import resolve_ch
from crewai_custom_tools.tools.genealogy.geo.transitions import apply_transition, load_transitions
from crewai_custom_tools.tools.genealogy.geo.usa import resolve_us
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace, ResolvedPlace

# Résolveurs autoritaires par pays. Ajouter un pays = une ligne (générique).
_BY_COUNTRY = {
    # Les communes fusionnées sont absentes de /communes : si resolve_fr rend None,
    # on tente /communes_associees_deleguees AVANT le repli Nominatim, qui perdrait
    # la hiérarchie. Le branchement est ici et non dans resolve_fr, parce que
    # france_ex_communes importe map_commune depuis france (sinon : cycle).
    # Nota : un résultat ambigu est truthy -> pas de repli, c'est voulu.
    "France": lambda p: resolve_fr(p) or resolve_fr_ex_commune(p),
    "Suisse": lambda p: resolve_ch(p),
    "Allemagne": lambda p: resolve_de(p),
    "États-Unis": lambda p: resolve_us(p),
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
    if resolved.ambiguous:
        return "proposition"                 # ambiguity wins over any score, incl. 1.0
    if resolved.score >= 1.0:
        return "ecrire"
    if resolved.score >= min_score:
        return "ecrire"
    return "proposition"


def confiance_of(resolved: ResolvedPlace | None, min_score: float = 0.90) -> str:
    if resolved is None or resolved.ambiguous:
        return "basse"
    if resolved.score >= 1.0:
        return "haute"
    if resolved.score >= min_score:
        return "moyenne"
    return "basse"
