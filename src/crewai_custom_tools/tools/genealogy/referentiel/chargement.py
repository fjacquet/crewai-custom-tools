"""Transport du référentiel : appels Wikidata temporisés, avec reprises.

Un pays qui échoue après reprises est *signalé*, pas fatal : les autres sont livrés.
Wikidata a rendu un 502 dès le second pays pendant la conception du chantier.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field
from requests.exceptions import RequestException

from crewai_custom_tools.core.rate_limiter import get_rate_limiter
from crewai_custom_tools.tools.genealogy.geo.france_ex_communes import parse_wkt_point
from crewai_custom_tools.tools.genealogy.models.domain import (
    CollisionIso, EntiteEcartee, Subdivision,
)
from crewai_custom_tools.tools.genealogy.referentiel.config import PaysReferentiel
from crewai_custom_tools.tools.genealogy.referentiel.wikidata import (
    build_query, build_query_pays, map_subdivisions, qid_of,
)
from crewai_custom_tools.tools.web.wikidata import sparql_rows

_PROVIDER = "Wikidata"
_TIMEOUT = 120.0


class ResultatPays(BaseModel):
    """Ce qu'un pays a rendu : ses subdivisions, ses collisions, ou son erreur."""

    code_iso: str
    subdivisions: list[Subdivision] = Field(default_factory=list)
    collisions: list[CollisionIso] = Field(default_factory=list)
    ecartees: list[EntiteEcartee] = Field(default_factory=list)
    erreur: str | None = None


class EntitePays(BaseModel):
    """Le pays lui-même : ce qu'on posera sur son lieu Gramps."""

    qid: str
    libelle_fr: str
    lat: str | None = None
    long: str | None = None
    frwiki: str | None = None


def _interroger(query: str, essais: int, pause: float) -> list[dict]:
    """Appel temporisé, avec reprises à attente croissante. Relève la dernière erreur."""
    derniere: Exception | None = None
    bornes = max(1, essais)  # `essais=0` (ou négatif) doit quand même essayer une fois
    for tentative in range(bornes):
        try:
            get_rate_limiter().acquire(_PROVIDER)
            return sparql_rows(query, timeout=_TIMEOUT)
        except RequestException as exc:
            derniere = exc
            if tentative < bornes - 1:
                time.sleep(pause * (tentative + 1))
    raise derniere if derniere else RuntimeError("échec sans exception")


def charger_pays(pays: PaysReferentiel, *, essais: int = 3,
                 pause: float = 5.0) -> ResultatPays:
    """Interroge Wikidata pour un pays et applique le mapper. N'lève jamais."""
    try:
        rows = _interroger(build_query(pays.code_iso, pays.langue, pays.qid), essais, pause)
    except RequestException as exc:
        return ResultatPays(code_iso=pays.code_iso, erreur=str(exc))
    subdivisions, collisions, ecartees = map_subdivisions(rows, pays)
    return ResultatPays(code_iso=pays.code_iso, subdivisions=subdivisions,
                        collisions=collisions, ecartees=ecartees)


def charger_entites_pays(qids: list[str], *, essais: int = 3,
                         pause: float = 5.0) -> dict[str, EntitePays]:
    """Les pays eux-mêmes, en un seul appel. Dictionnaire vide si l'appel échoue."""
    try:
        rows = _interroger(build_query_pays(qids), essais, pause)
    except RequestException:
        return {}
    entites: dict[str, EntitePays] = {}
    for row in rows:
        qid = qid_of(row.get("item"))
        if not qid or qid in entites:
            continue
        lat, long = (parse_wkt_point(row.get("coord")) or (None, None))
        entites[qid] = EntitePays(qid=qid, libelle_fr=row.get("itemLabel", ""),
                                  lat=lat, long=long, frwiki=row.get("art"))
    return entites
