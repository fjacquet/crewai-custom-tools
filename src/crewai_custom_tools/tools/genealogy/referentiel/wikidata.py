"""Requêtes Wikidata du référentiel : construction pure, puis transport isolé.

Le sélecteur est le code ISO 3166-2 (`P300`) et non la classe `P31`. Vérifié le 2026-07-21 :
sélectionner par classe rate Naples et Milan, qui sont des *villes métropolitaines* et non des
provinces. Le filtre par sous-classes (`P31/P279*` vers Q56061) a été essayé puis rejeté —
l'endpoint public rend un 504 sur la fermeture transitive.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from crewai_custom_tools.tools.genealogy.geo.france_ex_communes import parse_wkt_point
from crewai_custom_tools.tools.genealogy.models.domain import (
    CollisionIso,
    EntiteEcartee,
    Subdivision,
)
from crewai_custom_tools.tools.genealogy.referentiel.config import PaysReferentiel

_NIVEAU_IMPOSSIBLE = 99

_SUBDIVISIONS = """SELECT ?item ?itemLabel ?nomLocal ?iso ?coord ?parent ?art ?ancre WHERE {{
  ?item wdt:P300 ?iso .
  FILTER(STRSTARTS(?iso, "{prefixe}-"))
  FILTER NOT EXISTS {{ ?item wdt:P576 ?dissous }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
  OPTIONAL {{ ?item wdt:P131 ?parent }}
  OPTIONAL {{ ?item rdfs:label ?nomLocal . FILTER(lang(?nomLocal) = "{langue}") }}
  OPTIONAL {{ ?art schema:about ?item ; schema:isPartOf <https://fr.wikipedia.org/> }}
  OPTIONAL {{ ?item (wdt:P131|wdt:P131/wdt:P131|wdt:P131/wdt:P131/wdt:P131) wd:{qid_pays} .
              BIND(true AS ?ancre) }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
}}"""

_PAYS = """SELECT ?item ?itemLabel ?coord ?art WHERE {{
  VALUES ?item {{ {valeurs} }}
  OPTIONAL {{ ?item wdt:P625 ?coord }}
  OPTIONAL {{ ?art schema:about ?item ; schema:isPartOf <https://fr.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,en". }}
}}"""


def build_query(prefixe: str, langue: str, qid_pays: str) -> str:
    """Requête des subdivisions d'un pays, par préfixe ISO 3166-2 ('FR', 'CH'…).

    `langue` rapatrie le nom vernaculaire en plus du libellé français : c'est la seule prise
    pour apparier `Bayern`, déjà en base en allemand, avant qu'un QID n'y soit posé.

    `qid_pays` sert l'**ancre** : une entité dont le pays est atteignable en un à trois sauts
    de `P131` est de premier niveau, même si le conteneur qui l'en sépare n'a pas de code ISO.
    Sans cette ancre, les régions françaises — qui pendent sous `Q212429` France métropolitaine —
    tombent toutes, et les 96 départements avec elles.
    """
    return _SUBDIVISIONS.format(prefixe=prefixe, langue=langue, qid_pays=qid_pays)


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
                                          "coord": None, "art": None, "ancre": False})
        parent = qid_of(row.get("parent"))
        if parent:
            entree["parents"].add(parent)
        entree["coord"] = entree["coord"] or row.get("coord")
        entree["art"] = entree["art"] or row.get("art")
        entree["nom_local"] = entree["nom_local"] or row.get("nomLocal")
        # `BIND(true AS ?ancre)` ne rend la variable que si le pays est atteignable ; le drapeau
        # est donc vrai dès qu'UNE ligne de l'entité le porte, quel que soit l'ordre des lignes.
        entree["ancre"] = entree["ancre"] or str(row.get("ancre", "")).lower() == "true"
    return par_qid


def _noms(entree: dict) -> list[str]:
    """Noms d'appariement, français d'abord, vernaculaire ensuite, sans répétition."""
    noms = [n for n in (entree["label"], entree["nom_local"]) if n]
    return list(dict.fromkeys(noms))


def _candidats(entree: dict, par_qid: dict[str, dict]) -> list[str]:
    """Parents recevables : dans l'univers, et de code ISO différent de celui de l'enfant.

    La comparaison des codes est indispensable : sans elle, deux entités en collision se
    prennent mutuellement pour parent et aucune ne se résout — cas réel de `FR-69`, où
    Wikidata donne bien `Q46130 wdt:P131 Q18914778`.
    """
    return sorted(p for p in entree["parents"]
                  if p in par_qid and par_qid[p]["iso"] != entree["iso"])


def _moins_profond(candidats: list[str],
                   profondeur: Callable[[str], int]) -> tuple[str | None, int]:
    """Le candidat le MOINS profond, départagé à égalité par le plus petit QID.

    Unique implémentation du départage, partagée par le calcul du niveau (`_niveaux`) et par
    le choix du parent inscrit (`_parent_retenu`). Deux implémentations qui doivent s'accorder
    finissent toujours par diverger, et la base porterait alors une hiérarchie contredisant le
    niveau annoncé — un département de niveau 2 rattaché au pays.

    `profondeur` rend le niveau d'un candidat ; `_NIVEAU_IMPOSSIBLE` écarte le candidat.
    Rend `(None, _NIVEAU_IMPOSSIBLE)` quand aucun candidat n'est exploitable.
    """
    exploitables = [(profondeur(p), p) for p in candidats]
    exploitables = [(d, p) for d, p in exploitables if d < _NIVEAU_IMPOSSIBLE]
    if not exploitables:
        return None, _NIVEAU_IMPOSSIBLE
    profondeur_min, parent = min(exploitables)   # tuple : profondeur d'abord, QID ensuite
    return parent, profondeur_min


def _niveaux(par_qid: dict[str, dict], qid_pays: str) -> dict[str, int]:
    """Niveau de chaque entité : 1 + celui du parent le MOINS profond, ou 1 par l'ancre.

    Le parent le moins profond l'emporte parce que le rattachement le plus direct fait foi :
    le Bas-Rhin pend sous la Collectivité européenne d'Alsace *et* sous le Grand Est ; retenir
    le plus profond le classerait au niveau 3 et le ferait écarter.

    L'ancre ne s'applique qu'aux entités dont AUCUN `P131` ne pointe dans l'univers. Sans cette
    condition, Venise-la-ville — dont l'unique parent porte le même code ISO qu'elle, donc n'est
    pas candidat — serait promue au rang de région.

    `qid_pays in parents` double le drapeau `?ancre` : sur une charge réelle il est redondant
    (le pays à un saut allume l'ancre), mais il tient pour des lignes construites à la main,
    où la variable `?ancre` peut manquer alors que le rattachement au pays est explicite.
    """
    candidats = {q: _candidats(e, par_qid) for q, e in par_qid.items()}
    dans_univers = {q: any(p in par_qid for p in e["parents"]) for q, e in par_qid.items()}
    memo: dict[str, int] = {}

    def niveau(qid: str, vus: frozenset) -> int:
        if qid in memo:
            return memo[qid]
        if qid in vus:                                   # cycle de rattachement
            return _NIVEAU_IMPOSSIBLE
        entree = par_qid[qid]
        resultat = _NIVEAU_IMPOSSIBLE
        _, profondeur = _moins_profond(candidats[qid], lambda p: niveau(p, vus | {qid}))
        if profondeur < _NIVEAU_IMPOSSIBLE:
            resultat = profondeur + 1
        elif not dans_univers[qid] and (entree["ancre"] or qid_pays in entree["parents"]
                                        or not entree["parents"]):
            resultat = 1
        if not vus:                                      # ne mémoïser que les appels racines
            memo[qid] = resultat
        return resultat

    return {qid: niveau(qid, frozenset()) for qid in par_qid}


def _parent_retenu(qid: str, par_qid: dict[str, dict], niveaux: dict[str, int],
                   qid_pays: str) -> str:
    """Le parent effectivement inscrit : celui-là même qui a servi à calculer le niveau.

    Le départage n'est pas réécrit ici — il est délégué à `_moins_profond`, appelé avec la
    table des niveaux déjà résolue. Un parent qui divergerait de celui du calcul écrirait en
    base une hiérarchie contredisant le niveau annoncé.

    Sans candidat, l'entité tient son niveau 1 de l'ancre : son parent est le pays.
    """
    parent, _ = _moins_profond(_candidats(par_qid[qid], par_qid), niveaux.__getitem__)
    return parent if parent is not None else qid_pays


def map_subdivisions(
    rows: list[dict], pays: PaysReferentiel,
) -> tuple[list[Subdivision], list[CollisionIso], list[EntiteEcartee]]:
    """Charge SPARQL -> subdivisions retenues, collisions, écartées. Pure, hors ligne.

    Les cinq règles de la spec §3.4. Toute entité de la charge ressort dans exactement une des
    trois listes : rien ne disparaît en silence.
    """
    par_qid = _grouper(rows)
    niveaux = _niveaux(par_qid, pays.qid)

    retenues: list[Subdivision] = []
    ecartees: list[EntiteEcartee] = []
    for qid, entree in sorted(par_qid.items()):
        niveau = niveaux[qid]
        if niveau > len(pays.niveaux):
            motif = ("rattachement introuvable" if niveau >= _NIVEAU_IMPOSSIBLE
                     else f"niveau {niveau}, or {pays.nom} en compte {len(pays.niveaux)}")
            ecartees.append(EntiteEcartee(qid=qid, iso=entree["iso"],
                                          libelle_fr=entree["label"], motif=motif))
            continue
        lat, long = (parse_wkt_point(entree["coord"]) or (None, None))
        retenues.append(Subdivision(
            qid=qid, iso=entree["iso"],
            code=code_sans_prefixe(entree["iso"], pays.code_iso),
            libelle_fr=entree["label"], noms=_noms(entree),
            place_type=pays.niveaux[niveau - 1], niveau=niveau,
            parent_qid=_parent_retenu(qid, par_qid, niveaux, pays.qid),
            lat=lat, long=long, frwiki=entree["art"]))

    # Règle 5 : un code ISO porté par deux entités retenues est indécidable -> aucune écriture.
    par_iso: dict[str, list[Subdivision]] = defaultdict(list)
    for sub in retenues:
        par_iso[sub.iso].append(sub)
    collisions = [CollisionIso(iso=iso, qids=[s.qid for s in sorted(lot, key=lambda s: s.qid)],
                               libelles=[s.libelle_fr for s in sorted(lot, key=lambda s: s.qid)])
                  for iso, lot in sorted(par_iso.items()) if len(lot) > 1]
    propres = [lot[0] for _, lot in sorted(par_iso.items()) if len(lot) == 1]
    return propres, collisions, ecartees
