"""Wikidata → Piste. Pure : la collecte passe par sparql_rows(), pas par ce module.

Seule source capable de pistes FORTES : ses propriétés sont structurées, donc on
peut en tirer plusieurs facteurs distincts. Réserve connue : Wikidata ne décrit
que des personnes notables, le rendement sur un arbre ordinaire sera faible.
"""

import re

from crewai_custom_tools.tools.genealogy.models.domain import PersonFacts, Piste
from crewai_custom_tools.tools.genealogy.pistes.matchid import event_iso, norm_nom

# La recherche passe par le service INDEXÉ (mwapi/EntitySearch), jamais par un
# FILTER(CONTAINS(…)) sur rdfs:label : mesuré, ce dernier balaie les ~10 M d'humains
# de Wikidata et rend 504 Gateway Timeout après 65 s sur le point d'accès public.
# La version ci-dessous répond en ~0,9 s. Vérifiée en direct, pas supposée.
_SPARQL = """SELECT ?item ?itemLabel ?birthDate ?birthPlaceLabel ?p902 WHERE {{
  SERVICE wikibase:mwapi {{
    bd:serviceParam wikibase:api "EntitySearch" .
    bd:serviceParam wikibase:endpoint "www.wikidata.org" .
    bd:serviceParam mwapi:search "{nom}" .
    bd:serviceParam mwapi:language "fr" .
    bd:serviceParam mwapi:limit 25 .
    ?item wikibase:apiOutputItem mwapi:item .
  }}
  ?item wdt:P31 wd:Q5 .
  OPTIONAL {{ ?item wdt:P569 ?birthDate . }}
  OPTIONAL {{ ?item wdt:P19 ?birthPlace . }}
  OPTIONAL {{ ?item wdt:P902 ?p902 . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr,de,en". }}
}} LIMIT 25"""

_SEPARATEURS = re.compile(r"[,\-\s]+")


def mots(valeur: str) -> set[str]:
    """Découpe un nom en mots normalisés : virgules, espaces ET traits d'union.

    Mesuré sur l'arbre : 79 % des prénoms sont simples, 20 % sont des LISTES
    séparées par des virgules ('Marcel, Hubert, Andre' = trois prénoms distincts,
    pas un composé), 1 % portent un trait d'union ('Georges-Frédéric').

    Le trait d'union est éclaté volontairement : Wikidata répond
    'Guillaume Henri Dufour' à une recherche 'Guillaume-Henri Dufour' — vérifié.
    Sans éclatement, ce vrai positif serait perdu. Le patronyme devant lui aussi
    correspondre, la permissivité sur le prénom ne coûte rien.
    """
    return {norm_nom(m) for m in _SEPARATEURS.split(valeur or "") if m.strip()}


def requete_wikidata(person: PersonFacts) -> str:
    """La requête SPARQL exacte, rejouable telle quelle. Pure."""
    nom = f"{person.given} {person.surname}".strip()
    return _SPARQL.format(nom=nom.replace('"', ""))


def q_item(uri: str) -> str:
    """"http://www.wikidata.org/entity/Q42" -> "Q42". Chaîne vide si non reconnaissable."""
    return uri.rsplit("/", 1)[-1] if uri else ""


def pistes_wikidata(person: PersonFacts, resultats: list[dict]) -> list[Piste]:
    """Une piste par résultat SPARQL portant AU MOINS une concordance. N'écrit rien, ne conclut rien.

    Un résultat sans aucun facteur concordant est écarté : `EntitySearch` est une
    recherche floue sur le nom, et sans rien qui corrobore, il ne s'agit que de la
    sortie brute du moteur de recherche, pas d'une piste.
    """
    requete = requete_wikidata(person)
    naissance_arbre = event_iso(person.birth)
    lieu_arbre = person.birth.place_name if person.birth else ""
    pistes: list[Piste] = []
    for row in resultats:
        identite = q_item(row.get("item", ""))
        if not identite:
            continue
        concordances: list[str] = []
        divergences: list[str] = []

        # Comparaison par MOTS ENTIERS des deux côtés, jamais par sous-chaîne :
        # `norm_nom(surname) in norm_nom(label)` ferait correspondre « Roy » à
        # « LEROY » et fabriquerait des pistes fortes fausses — or une piste forte
        # est ÉCRITE dans l'arbre, une faible reste dans le rapport.
        # On exige le patronyme ET au moins un prénom commun.
        mots_label = mots(row.get("itemLabel", ""))
        if mots_label and mots(person.surname) <= mots_label and (
                mots(person.given) & mots_label):
            concordances.append("nom")

        # wdt:P569 rend un dateTime complet quelle que soit la précision réelle ;
        # on ne compare donc que les 10 premiers caractères, et seulement si
        # l'arbre porte lui aussi une date COMPLÈTE (10 caractères).
        naissance_wd = (row.get("birthDate") or "")[:10]
        if len(naissance_wd) == 10 and len(naissance_arbre) == 10:
            if naissance_wd == naissance_arbre:
                concordances.append("date complète")
            else:
                divergences.append("dates de naissance différentes")

        lieu_wd = row.get("birthPlaceLabel", "")
        if lieu_arbre and lieu_wd and norm_nom(lieu_arbre) == norm_nom(lieu_wd):
            concordances.append("lieu")

        # EntitySearch est une recherche FLOUE : sans aucune concordance, une
        # ligne n'est que du bruit du moteur de recherche, pas une piste. Une
        # divergence seule (sans rien qui corrobore) ne suffit pas non plus —
        # mesuré sur 40 personnes réelles : 13/21 pistes Wikidata n'avaient
        # aucun facteur de concordance.
        if not concordances:
            continue

        pistes.append(Piste(
            gramps_id=person.gramps_id, handle=person.handle,
            source="wikidata", identite=identite,
            url=row.get("item") or None,
            requete=requete,
            concordances=concordances, divergences=divergences,
        ))
    return pistes
