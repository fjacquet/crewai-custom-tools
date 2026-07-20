"""Résolveur des ex-communes françaises (communes associées / déléguées).

geo.api.gouv.fr/communes ne connaît que les communes VIVANTES : une commune fusionnée
(loi Marcellin, 1971) y est introuvable, et `resolve_fr` bascule alors sur Nominatim,
qui perd la hiérarchie. L'endpoint /communes_associees_deleguees les connaît, mais ne
donne aucune date de fusion — Wikidata la fournit (P576).

On ne date les rattachements que si les deux sources concordent sur le successeur.
"""

from __future__ import annotations

import re

import requests
from pydantic import BaseModel

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
    """Faits Wikidata pour une ex-commune. None si 0 ou >1 entité porte ce code INSEE.

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
    if len(rows) != 1:                     # 0 = inconnu ; >1 = ambigu -> on ne date pas
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
