"""Gallica (BnF) → Piste. Pure : la collecte passe par GallicaSearchTool.

La presse ne sert pas à RETROUVER une personne mais à la CONTEXTUALISER : on
n'émet que pour des personnes dont la date ET le lieu sont connus, et ces
bornes filtrent les résultats. Les pistes seront presque toujours faibles —
un journal donne le nom, jamais une date d'état civil. C'est voulu.
"""

import re

from crewai_custom_tools.tools.genealogy.models.domain import PersonFacts, Piste
from crewai_custom_tools.tools.genealogy.pistes.matchid import event_iso, norm_nom

_AGE_MAX = 105  # la borne de R2 : au-delà, l'audit signale déjà une anomalie
_ARK = re.compile(r"(ark:/\d+/[A-Za-z0-9]+)")


def personne_eligible(person: PersonFacts) -> bool:
    """Date de naissance COMPLÈTE et lieu connus — sinon on n'interroge pas."""
    if person.birth is None:
        return False
    return len(event_iso(person.birth)) == 10 and bool(person.birth.place_name)


def fenetre_vie(person: PersonFacts) -> tuple[int, int]:
    """(année_min, année_max). Sans décès connu, on borne à 105 ans."""
    debut = person.birth.year if person.birth and person.birth.year else 0
    if person.death is not None and person.death.year:
        return debut, person.death.year
    return debut, debut + _AGE_MAX


def requete_gallica(person: PersonFacts) -> str:
    """La requête CQL exacte, rejouable telle quelle."""
    lieu = person.birth.place_name if person.birth else ""
    return f'gallica all "{person.surname} {person.given} {lieu}"'.strip()


def ark_de(url: str) -> str:
    """Extrait l'ark d'une URL Gallica. Chaîne vide si absent — jamais fabriqué."""
    trouve = _ARK.search(url or "")
    return trouve.group(1) if trouve else ""


def _annee(valeur: str) -> int | None:
    trouve = re.search(r"\d{4}", valeur or "")
    return int(trouve.group(0)) if trouve else None


def pistes_gallica(person: PersonFacts, resultats: list[dict]) -> list[Piste]:
    """Une piste par enregistrement SRU retenu. N'écrit rien, ne conclut rien."""
    if not personne_eligible(person):
        return []
    debut, fin = fenetre_vie(person)
    requete = requete_gallica(person)
    lieu_arbre = person.birth.place_name if person.birth else ""
    pistes: list[Piste] = []
    for rec in resultats:
        # Sans ark, pas de permalien : on n'invente pas d'URL (cf. Mémoire des hommes).
        identite = ark_de(rec.get("url", ""))
        if not identite:
            continue
        annee = _annee(rec.get("date", ""))
        if annee is None or not (debut <= annee <= fin):
            continue
        concordances: list[str] = []
        titre = rec.get("title", "")
        if norm_nom(person.surname) in norm_nom(titre):
            concordances.append("nom")
        if lieu_arbre and norm_nom(lieu_arbre) in norm_nom(titre):
            concordances.append("lieu")
        pistes.append(Piste(
            gramps_id=person.gramps_id, handle=person.handle,
            source="gallica", identite=identite, identite_derivee=False,
            url=rec.get("url") or None,
            requete=requete,
            concordances=concordances, divergences=[],
        ))
    return pistes
