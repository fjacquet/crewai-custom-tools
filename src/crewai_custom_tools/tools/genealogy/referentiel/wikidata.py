"""Requêtes Wikidata du référentiel : construction pure, puis transport isolé.

Le sélecteur est le code ISO 3166-2 (`P300`) et non la classe `P31`. Vérifié le 2026-07-21 :
sélectionner par classe rate Naples et Milan, qui sont des *villes métropolitaines* et non des
provinces. Le filtre par sous-classes (`P31/P279*` vers Q56061) a été essayé puis rejeté —
l'endpoint public rend un 504 sur la fermeture transitive.
"""

from __future__ import annotations

from collections import defaultdict

from crewai_custom_tools.tools.genealogy.geo.france_ex_communes import parse_wkt_point
from crewai_custom_tools.tools.genealogy.models.domain import CollisionIso, Subdivision
from crewai_custom_tools.tools.genealogy.referentiel.config import PaysReferentiel

_NIVEAU_IMPOSSIBLE = 99

_SUBDIVISIONS = """SELECT ?item ?itemLabel ?nomLocal ?iso ?coord ?parent ?art WHERE {{
  ?item wdt:P300 ?iso .
  FILTER(STRSTARTS(?iso, "{prefixe}-"))
  FILTER NOT EXISTS {{ ?item wdt:P576 ?dissous }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
  OPTIONAL {{ ?item wdt:P131 ?parent }}
  OPTIONAL {{ ?item rdfs:label ?nomLocal . FILTER(lang(?nomLocal) = "{langue}") }}
  OPTIONAL {{ ?art schema:about ?item ; schema:isPartOf <https://fr.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
}}"""

_PAYS = """SELECT ?item ?itemLabel ?coord ?art WHERE {{
  VALUES ?item {{ {valeurs} }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
  OPTIONAL {{ ?art schema:about ?item ; schema:isPartOf <https://fr.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
}}"""


def build_query(prefixe: str, langue: str) -> str:
    """Requête des subdivisions d'un pays, par préfixe ISO 3166-2 ('FR', 'CH'…).

    `langue` rapatrie le nom vernaculaire en plus du libellé français : c'est la seule prise
    pour apparier `Bayern`, déjà en base en allemand, avant qu'un QID n'y soit posé.
    """
    return _SUBDIVISIONS.format(prefixe=prefixe, langue=langue)


def build_query_pays(qids: list[str]) -> str:
    """Requête des pays eux-mêmes (libellé, centroïde, article), en un seul appel."""
    return _PAYS.format(valeurs=" ".join(f"wd:{q}" for q in qids))


def qid_of(uri: str | None) -> str:
    """'http://www.wikidata.org/entity/Q39' -> 'Q39'. Chaîne vide si rien à extraire."""
    if not uri:
        return ""
    return uri.rsplit("/", 1)[-1]


def code_sans_prefixe(iso: str, prefixe: str) -> str:
    """'FR-03' -> '03'. Reproduit la convention des codes déjà en base.

    Rendu tel quel si le préfixe ne correspond pas : mieux vaut un code inhabituel
    qu'un code tronqué au hasard.
    """
    debut = f"{prefixe}-"
    return iso[len(debut):] if iso.startswith(debut) else iso


def _grouper(rows: list[dict]) -> dict[str, dict]:
    """Regroupe les lignes aplaties par entité. SPARQL éclate les propriétés multivaluées :
    une entité à trois P131 revient sur trois lignes, et c'est bénin — on réunit ici."""
    par_qid: dict[str, dict] = {}
    for row in rows:
        qid = qid_of(row.get("item"))
        if not qid:
            continue
        entree = par_qid.setdefault(qid, {"qid": qid, "iso": row.get("iso", ""),
                                          "label": row.get("itemLabel", ""),
                                          "nom_local": None, "parents": set(),
                                          "coord": None, "art": None})
        parent = qid_of(row.get("parent"))
        if parent:
            entree["parents"].add(parent)
        entree["coord"] = entree["coord"] or row.get("coord")
        entree["art"] = entree["art"] or row.get("art")
        entree["nom_local"] = entree["nom_local"] or row.get("nomLocal")
    return par_qid


def _noms(entree: dict) -> list[str]:
    """Noms d'appariement, français d'abord, vernaculaire ensuite, sans répétition."""
    noms = [n for n in (entree["label"], entree["nom_local"]) if n]
    return list(dict.fromkeys(noms))


def _choisir_parent(entree: dict, par_qid: dict[str, dict], qid_pays: str) -> str | None:
    """Règle 2 : le parent est le P131 qui est lui-même candidat, à défaut le pays.

    Un parent portant le MÊME code ISO que l'enfant est ignoré : sans cela, deux entités
    en collision (FR-69) se prendraient mutuellement pour parent et aucune ne se résoudrait.
    """
    candidats = sorted(p for p in entree["parents"]
                       if p in par_qid and par_qid[p]["iso"] != entree["iso"])
    if candidats:
        return candidats[0]
    if qid_pays in entree["parents"]:
        return qid_pays
    return None


def _niveau(qid: str, parents: dict[str, str], qid_pays: str, vus: frozenset = frozenset()) -> int:
    """Règle 3 : 1 sous le pays, 1 + niveau(parent) sinon. Cycle ou orpheline -> impossible."""
    if qid in vus:
        return _NIVEAU_IMPOSSIBLE
    parent = parents.get(qid)
    if parent is None:
        return _NIVEAU_IMPOSSIBLE
    if parent == qid_pays:
        return 1
    return min(_NIVEAU_IMPOSSIBLE, 1 + _niveau(parent, parents, qid_pays, vus | {qid}))


def map_subdivisions(rows: list[dict],
                     pays: PaysReferentiel) -> tuple[list[Subdivision], list[CollisionIso]]:
    """Charge SPARQL -> subdivisions retenues + collisions signalées. Pure, hors ligne.

    Les cinq règles de la spec §3.4, dans l'ordre : univers ISO, parent, niveau, niveaux
    configurés, collision. Aucune liste de QID à exclure — vérifié le 2026-07-21, un code
    ISO correspond à une entité et une seule sauf trois exceptions, que ces règles traitent.
    """
    par_qid = _grouper(rows)
    parents = {}
    for qid, entree in par_qid.items():
        parent = _choisir_parent(entree, par_qid, pays.qid)
        if parent is not None:
            parents[qid] = parent

    retenues: list[Subdivision] = []
    for qid, entree in par_qid.items():
        if qid not in parents:
            continue                                    # règle 2 : aucun parent valide
        niveau = _niveau(qid, parents, pays.qid)
        if niveau > len(pays.niveaux):                  # règles 3 et 4
            continue
        lat, long = (parse_wkt_point(entree["coord"]) or (None, None))
        retenues.append(Subdivision(
            qid=qid, iso=entree["iso"],
            code=code_sans_prefixe(entree["iso"], pays.code_iso),
            libelle_fr=entree["label"], noms=_noms(entree),
            place_type=pays.niveaux[niveau - 1],
            niveau=niveau, parent_qid=parents[qid],
            lat=lat, long=long, frwiki=entree["art"]))

    # Règle 5 : un code ISO porté par deux entités retenues est indécidable -> aucune écriture.
    par_iso: dict[str, list[Subdivision]] = defaultdict(list)
    for sub in retenues:
        par_iso[sub.iso].append(sub)
    collisions = [CollisionIso(iso=iso, qids=[s.qid for s in lot],
                               libelles=[s.libelle_fr for s in lot])
                  for iso, lot in sorted(par_iso.items()) if len(lot) > 1]
    propres = [lot[0] for _, lot in sorted(par_iso.items()) if len(lot) == 1]
    return propres, collisions
