"""France resolver: authoritative INSEE-code → geo.api.gouv.fr commune."""

from __future__ import annotations

import httpx

from crewai_custom_tools.core.rate_limiter import get_rate_limiter
from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain, DatedName, ParsedPlace, PlaceLevel, ResolvedPlace,
)

_BASE = "https://geo.api.gouv.fr"
_FIELDS = "nom,code,centre,departement,region"
_PROVIDER = "GeoApiGouvFr"


def _http_get(path: str, params: dict) -> dict:
    """Thin HTTP GET (monkeypatched in tests). WGS84 GeoJSON out."""
    get_rate_limiter().acquire(_PROVIDER)
    resp = httpx.get(f"{_BASE}{path}", params=params, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def map_commune(payload: dict, parsed: ParsedPlace) -> ResolvedPlace:
    """Pure map of a geo.api.gouv.fr commune payload → authoritative ResolvedPlace."""
    lon, lat = payload["centre"]["coordinates"]            # GeoJSON = [lon, lat]
    dep = payload.get("departement") or {}
    reg = payload.get("region") or {}
    levels = [PlaceLevel(name="France", place_type="Country")]
    if reg.get("nom"):
        levels.append(PlaceLevel(name=reg["nom"], place_type="Region", code=reg.get("code")))
    if dep.get("nom"):
        levels.append(PlaceLevel(name=dep["nom"], place_type="Department", code=dep.get("code")))
    return ResolvedPlace(
        name=payload["nom"], place_type="Municipality",
        lat=str(lat), long=str(lon), code=payload.get("code"),
        chains=[DatedChain(levels=levels)],
        alt_names=[DatedName(value=parsed.raw)],
        score=1.0, source="geo.api.gouv.fr", query=f"/communes/{parsed.insee}",
    )


def resolve_fr(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Resolve a French place by embedded INSEE code (authoritative). None if no usable code."""
    if not parsed.insee:
        return None
    payload = _http_get(f"/communes/{parsed.insee}", {"fields": _FIELDS})
    if not isinstance(payload, dict) or "centre" not in payload:
        return None
    return map_commune(payload, parsed)
