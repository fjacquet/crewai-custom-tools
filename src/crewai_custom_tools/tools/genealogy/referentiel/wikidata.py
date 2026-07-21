"""Requêtes Wikidata du référentiel : construction pure, puis transport isolé.

Le sélecteur est le code ISO 3166-2 (`P300`) et non la classe `P31`. Vérifié le 2026-07-21 :
sélectionner par classe rate Naples et Milan, qui sont des *villes métropolitaines* et non des
provinces. Le filtre par sous-classes (`P31/P279*` vers Q56061) a été essayé puis rejeté —
l'endpoint public rend un 504 sur la fermeture transitive.
"""

from __future__ import annotations

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
