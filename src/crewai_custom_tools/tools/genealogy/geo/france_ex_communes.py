"""Résolveur des ex-communes françaises (communes associées / déléguées).

geo.api.gouv.fr/communes ne connaît que les communes VIVANTES : une commune fusionnée
(loi Marcellin, 1971) y est introuvable, et `resolve_fr` bascule alors sur Nominatim,
qui perd la hiérarchie. L'endpoint /communes_associees_deleguees les connaît, mais ne
donne aucune date de fusion — Wikidata la fournit (P576).

On ne date les rattachements que si les deux sources concordent sur le successeur.
"""

from __future__ import annotations

import re

import httpx
import requests
from pydantic import BaseModel

from crewai_custom_tools.core.rate_limiter import get_rate_limiter
from crewai_custom_tools.tools.genealogy.geo.france import _FIELDS as _COMMUNE_FIELDS
from crewai_custom_tools.tools.genealogy.geo.france import map_commune, pick_exact_by_name
from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain, DatedName, ParsedPlace, PlaceLevel, ResolvedPlace,
)
from crewai_custom_tools.tools.web.wikidata import sparql_rows

_WKT_POINT_RE = re.compile(r"^\s*Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)\s*$", re.IGNORECASE)

# Une seule requête rend la dissolution, le successeur ET le GPS : la garde de
# recoupement (successeur vs chefLieu) ne coûte donc aucun appel supplémentaire.
_SPARQL = """SELECT ?item ?dissolved ?succInsee ?coord WHERE {{
  ?item wdt:P374 "{insee}" .
  OPTIONAL {{ ?item wdt:P576 ?dissolved }}
  OPTIONAL {{ ?item wdt:P1366 ?succ . ?succ wdt:P374 ?succInsee }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
}} LIMIT 10"""


class ExCommuneFacts(BaseModel):
    """Ce que Wikidata sait d'une ex-commune, identifiée par son code INSEE."""

    dissolved: str | None = None          # "YYYY-MM-DD"
    successor_insee: str | None = None
    lat: str | None = None                # WGS84 décimal
    long: str | None = None


def parse_wkt_point(wkt: str) -> tuple[str, str] | None:
    """'Point(lon lat)' -> ('lat', 'long'). None si non parsable.

    ATTENTION : le WKT met la LONGITUDE en premier, comme GeoJSON. Inverser rendrait
    des coordonnées parfaitement bien formées, et fausses.
    """
    match = _WKT_POINT_RE.match(wkt or "")
    if match is None:
        return None
    lon, lat = match.group(1), match.group(2)
    return lat, lon


def wikidata_ex_commune(insee: str) -> ExCommuneFacts | None:
    """Faits Wikidata pour une ex-commune. None si 0, ou >1 entité *distincte*, porte ce code INSEE.

    Wikidata n'est qu'un enrichisseur : toute panne réseau rend None (pas de datation)
    plutôt que de faire échouer la résolution entière.
    """
    try:
        rows = sparql_rows(_SPARQL.format(insee=insee))
    except requests.RequestException:
        # Réseau ET JSON malformé (JSONDecodeError hérite de RequestException).
        # Volontairement étroit : un KeyError ou une ValidationError seraient des
        # bugs de ce module, et doivent remonter plutôt que se déguiser en
        # « pas de datation » — même convention que places_apply.py.
        return None
    if not rows:                           # 0 ligne : code INSEE inconnu de Wikidata
        return None
    items = {row.get("item") for row in rows}
    if len(items) != 1:
        # On compte les ?item DISTINCTS, pas les lignes : les trois OPTIONAL de la
        # requête produisent un fan-out SPARQL dès qu'une propriété est multivaluée
        # (P625 porte couramment plusieurs revendications de coordonnées pour un
        # même lieu) — plusieurs lignes pour une seule et même entité, ce n'est pas
        # une ambiguïté. On ne refuse de dater que si les lignes rendent effectivement
        # plus d'une entité distincte.
        return None
    row = rows[0]
    lat = long = None
    if row.get("coord"):
        point = parse_wkt_point(row["coord"])
        if point is not None:
            lat, long = point
    dissolved = row.get("dissolved")
    return ExCommuneFacts(
        dissolved=dissolved.split("T")[0] if dissolved else None,
        successor_insee=row.get("succInsee"),
        lat=lat, long=long,
    )


_BASE = "https://geo.api.gouv.fr"
_ASSOCIEE_FIELDS = "nom,code,type,chefLieu,centre,departement,region"
_PROVIDER = "GeoApiGouvFr"


def _http_get(path: str, params: dict):
    """Thin HTTP GET (monkeypatché dans les tests). WGS84 GeoJSON en sortie."""
    get_rate_limiter().acquire(_PROVIDER)
    resp = httpx.get(f"{_BASE}{path}", params=params, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def resolve_fr_ex_commune(parsed: ParsedPlace) -> ResolvedPlace | None:
    """Résout une commune française fusionnée (associée/déléguée).

    Deux chaînes datées quand geo.api.gouv.fr et Wikidata s'accordent sur le
    successeur ; sinon une seule chaîne non datée — jamais de date inventée.
    """
    if not parsed.commune:
        return None
    results = _http_get("/communes_associees_deleguees",
                        {"nom": parsed.commune, "fields": _ASSOCIEE_FIELDS, "limit": 10})
    if not isinstance(results, list) or not results:
        return None
    exact = pick_exact_by_name(results, parsed)
    if not exact:
        return None                                  # repli Nominatim côté registre
    ex = exact[0]
    chef_code = ex.get("chefLieu")
    if not chef_code:
        return None
    chef = _http_get(f"/communes/{chef_code}", {"fields": _COMMUNE_FIELDS})
    if not isinstance(chef, dict) or "centre" not in chef:
        return None
    # map_commune est réutilisé pour la hiérarchie France>Région>Département, déjà testée.
    modern = map_commune(chef, parsed)
    parents = list(modern.chains[0].levels)
    chef_level = PlaceLevel(name=modern.name, place_type="Municipality", code=modern.code)

    facts = wikidata_ex_commune(ex["code"])
    # Garde de recoupement : on ne date que si les DEUX sources désignent le même
    # successeur. Une date de fusion fausse route silencieusement les événements
    # vers la mauvaise branche — pire qu'une date absente.
    concordant = (facts is not None and facts.dissolved
                  and facts.successor_insee == chef_code)
    if concordant:
        chains = [
            DatedChain(levels=parents, date_qualifier=f"avant {facts.dissolved}"),
            DatedChain(levels=parents + [chef_level],
                       date_qualifier=f"après {facts.dissolved}"),
        ]
        source = "geo.api.gouv.fr/communes_associees_deleguees + Wikidata"
    else:
        chains = [DatedChain(levels=parents + [chef_level])]
        source = "geo.api.gouv.fr/communes_associees_deleguees"

    # GPS : Wikidata (centre du bourg) de préférence au `centre` de l'API, qui est le
    # centroïde du territoire — mesuré à ~700 m du village sur Saint-Agnant. En
    # généalogie on veut l'église, pas le barycentre cadastral. Exception assumée à
    # map_commune, qui prend toujours le centre de l'API pour les communes vivantes.
    lon, lat = (ex.get("centre") or {}).get("coordinates", [None, None])
    if facts is not None and facts.lat and facts.long:
        lat, lon = facts.lat, facts.long

    resolved = ResolvedPlace(
        name=ex["nom"], place_type="Municipality",
        lat=str(lat) if lat is not None else None,
        long=str(lon) if lon is not None else None,
        code=ex["code"], chains=chains,
        alt_names=[DatedName(value=parsed.raw)],
        score=1.0, source=source,
        query=f"/communes_associees_deleguees?nom={parsed.commune}",
    )
    if len(exact) > 1:
        resolved.ambiguous = True                    # vrais homonymes -> proposition
        resolved.source = f"{source} ({len(exact)} homonymes)"
    return resolved
