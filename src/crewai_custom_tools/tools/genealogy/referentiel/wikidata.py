"""Requêtes Wikidata du référentiel : construction pure, puis transport isolé.

Le sélecteur est le code ISO 3166-2 (`P300`) et non la classe `P31`. Vérifié le 2026-07-21 :
sélectionner par classe rate Naples et Milan, qui sont des *villes métropolitaines* et non des
provinces. Le filtre par sous-classes (`P31/P279*` vers Q56061) a été essayé puis rejeté —
l'endpoint public rend un 504 sur la fermeture transitive.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable

from crewai_custom_tools.tools.genealogy.geo.france_ex_communes import parse_wkt_point
from crewai_custom_tools.tools.genealogy.models.domain import (
    CollisionIso,
    EntiteEcartee,
    Subdivision,
)
from crewai_custom_tools.tools.genealogy.referentiel.config import PaysReferentiel

# Sentinelle hors du domaine des niveaux réels : un entier comme 99 s'additionne sans bruit
# (« 98 + 1 ») et se compare comme un niveau, alors qu'il signifie « rattachement introuvable ».
_NIVEAU_IMPOSSIBLE = math.inf

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


_COLONNES = (("iso", "iso"), ("label", "itemLabel"), ("nom_local", "nomLocal"),
             ("coord", "coord"), ("art", "art"))


def _plus_petite(actuelle: str | None, proposee: str | None) -> str | None:
    """Retient la plus petite valeur vue, jamais la première arrivée.

    P625 n'est pas plus monovalué que P131 : `Q102317` Kielce porte deux coordonnées
    distinctes. Prendre la première rendrait la sortie dépendante de l'ordre des lignes, que
    SPARQL ne garantit pas. L'ordre lexicographique n'a pas de sens géographique — il n'est
    là que pour être stable, et le choix reste arbitraire par nature.

    **Ce que ce départage perd, et pourquoi c'est toléré** : appliqué à `iso`, il fait
    disparaître sans trace le second code d'une entité qui en porte deux du même préfixe.
    Le cas existe — `Q1142` Alsace porte `FR-A` *et* `FR-6AE` — mais il est hors des charges
    actuelles, filtré par `P576`. La partition garantie par `map_subdivisions` porte sur les
    **QID**, pas sur les codes : l'entité ressort toujours dans l'une des trois listes, seul
    son code surnuméraire est muet. Le référentiel écrit un lieu par entité et non un par
    code ; porter les deux demanderait un modèle à codes multiples, hors sujet ici.
    """
    if proposee is None:
        return actuelle
    return proposee if actuelle is None else min(actuelle, proposee)


def _grouper(rows: list[dict]) -> dict[str, dict]:
    """Regroupe les lignes aplaties par entité. SPARQL éclate les propriétés multivaluées :
    une entité à trois P131 revient sur trois lignes, et c'est bénin — on réunit ici.

    Toute réunion est indépendante de l'ordre des lignes : union pour les parents, disjonction
    pour l'ancre, plus petite valeur pour les colonnes scalaires.
    """
    par_qid: dict[str, dict] = {}
    for row in rows:
        qid = qid_of(row.get("item"))
        if not qid:
            continue
        entree = par_qid.setdefault(qid, {"qid": qid, "iso": None, "label": None,
                                          "nom_local": None, "parents": set(),
                                          "coord": None, "art": None, "ancre": False})
        parent = qid_of(row.get("parent"))
        if parent:
            entree["parents"].add(parent)
        for cle, colonne in _COLONNES:
            entree[cle] = _plus_petite(entree[cle], row.get(colonne))
        # `BIND(true AS ?ancre)` ne rend la variable que si le pays est atteignable ; le drapeau
        # est donc vrai dès qu'UNE ligne de l'entité le porte, quel que soit l'ordre des lignes.
        entree["ancre"] = entree["ancre"] or str(row.get("ancre", "")).lower() == "true"
    for entree in par_qid.values():          # `iso` et `label` alimentent des champs `str`
        entree["iso"] = entree["iso"] or ""
        entree["label"] = entree["label"] or ""
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
                   profondeur: Callable[[str], float]) -> tuple[str | None, float]:
    """Le candidat le MOINS profond, départagé à égalité par le plus petit QID.

    Unique implémentation du départage, partagée par le calcul du niveau (`_niveaux`) et par
    le choix du parent inscrit (`_parent_retenu`). Deux implémentations qui doivent s'accorder
    finissent toujours par diverger, et la base porterait alors une hiérarchie contredisant le
    niveau annoncé — un département de niveau 2 rattaché au pays.

    `profondeur` rend le niveau d'un candidat ; `_NIVEAU_IMPOSSIBLE` l'écarte.
    Rend `(None, _NIVEAU_IMPOSSIBLE)` quand aucun candidat n'est exploitable.
    """
    exploitables = [(profondeur(p), p) for p in candidats]
    exploitables = [(d, p) for d, p in exploitables if d < _NIVEAU_IMPOSSIBLE]
    if not exploitables:
        return None, _NIVEAU_IMPOSSIBLE
    profondeur_min, parent = min(exploitables)   # tuple : profondeur d'abord, QID ensuite
    return parent, profondeur_min


def _niveaux(par_qid: dict[str, dict]) -> dict[str, float]:
    """Niveau de chaque entité : 1 + celui du parent le MOINS profond, ou 1 par l'ancre.

    Point fixe itératif, et non récursion : on part des entités de premier niveau, puis on
    relâche `niveau(enfant) = 1 + min(niveau des parents candidats)` jusqu'à stabilisation.
    La version récursive coupait les cycles par un ensemble de sommets visités, ce qui
    interdisait de mémoïser les appels contraints — donc un coût exponentiel sur un graphe
    `P131` dense (mesuré : 24 entités, 10,5 s). Ici c'est O(V·E), sans récursion, et les
    cycles se règlent d'eux-mêmes : un sommet qu'aucune ancre n'atteint reste à l'infini.

    Le parent le moins profond l'emporte parce que le rattachement le plus direct fait foi :
    le Bas-Rhin pend sous la Collectivité européenne d'Alsace *et* sous le Grand Est ; retenir
    le plus profond le classerait au niveau 3 et le ferait écarter.

    L'ancre ne s'applique qu'aux entités dont AUCUN `P131` ne pointe dans l'univers. Sans cette
    condition, Venise-la-ville — dont l'unique parent porte le même code ISO qu'elle, donc n'est
    pas candidat — serait promue au rang de région.
    """
    candidats = {q: _candidats(e, par_qid) for q, e in par_qid.items()}
    dans_univers = {q: any(p in par_qid for p in e["parents"]) for q, e in par_qid.items()}
    # Amorce : sont de premier niveau les entités qu'aucun P131 ne rattache dans l'univers et
    # que l'ancre pays atteint — ou qui n'ont aucun P131 du tout.
    niveaux: dict[str, float] = {
        qid: (1.0 if not dans_univers[qid] and (e["ancre"] or not e["parents"])
              else _NIVEAU_IMPOSSIBLE)
        for qid, e in par_qid.items()}

    # Un plus court chemin est simple : |V| passes suffisent à le propager (Bellman-Ford).
    for _ in range(len(par_qid)):
        stable = True
        for qid in par_qid:
            _, profondeur = _moins_profond(candidats[qid], niveaux.__getitem__)
            if profondeur + 1 < niveaux[qid]:
                niveaux[qid] = profondeur + 1
                stable = False
        if stable:
            break
    return niveaux


def _parent_retenu(qid: str, par_qid: dict[str, dict], niveaux: dict[str, float],
                   qid_pays: str) -> str:
    """Le parent effectivement inscrit : celui-là même qui a servi à calculer le niveau.

    Le départage n'est pas réécrit ici — il est délégué à `_moins_profond`, appelé sur la
    table des niveaux stabilisée, celle-là même dont `_niveaux` a tiré le niveau. Un parent
    qui divergerait écrirait en base une hiérarchie contredisant le niveau annoncé.

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
    niveaux = _niveaux(par_qid)

    retenues: list[Subdivision] = []
    ecartees: list[EntiteEcartee] = []
    for qid, entree in sorted(par_qid.items()):
        profondeur = niveaux[qid]
        if profondeur > len(pays.niveaux):
            motif = ("rattachement introuvable" if profondeur == _NIVEAU_IMPOSSIBLE
                     else f"niveau {profondeur:.0f}, or {pays.nom} "
                          f"en compte {len(pays.niveaux)}")
            ecartees.append(EntiteEcartee(qid=qid, iso=entree["iso"],
                                          libelle_fr=entree["label"], motif=motif))
            continue
        niveau = int(profondeur)
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
