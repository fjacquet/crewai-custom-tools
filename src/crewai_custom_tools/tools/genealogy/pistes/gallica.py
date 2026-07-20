"""Gallica (BnF) → Piste. Pure : la collecte passe par GallicaSearchTool.

La presse ne sert pas à RETROUVER une personne mais à la CONTEXTUALISER : on
n'émet que pour des personnes dont la date ET le lieu sont connus, et ces
bornes filtrent les résultats. Les pistes seront presque toujours faibles —
un journal donne le nom, jamais une date d'état civil. C'est voulu.
"""

import re

from crewai_custom_tools.tools.genealogy.models.domain import PersonFacts, Piste
from crewai_custom_tools.tools.genealogy.pistes.matchid import event_iso, norm_nom
from crewai_custom_tools.tools.genealogy.pistes.wikidata import mots

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


_MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}
_DATE_NUM = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_TXT = re.compile(r"\b(\d{1,2})\s+([A-Za-zÉÛéûàç]+)\s+(\d{4})\b")


def dates_du_texte(texte: str) -> set[str]:
    """Toutes les dates COMPLÈTES d'un texte, en ISO. Pure.

    Trois formes rencontrées dans les titres de presse : « 14/07/1900 »,
    « 1900-07-14 » et « 14 juillet 1900 ». Une année seule n'est jamais
    rendue — elle ne constitue pas une date (règle cardinale du projet).
    """
    trouvees: set[str] = set()
    for j, m, a in _DATE_NUM.findall(texte or ""):
        trouvees.add(f"{int(a):04d}-{int(m):02d}-{int(j):02d}")
    for a, m, j in _DATE_ISO.findall(texte or ""):
        trouvees.add(f"{int(a):04d}-{int(m):02d}-{int(j):02d}")
    for j, mot, a in _DATE_TXT.findall(texte or ""):
        mois = _MOIS.get(norm_nom(mot).lower())
        if mois:
            trouvees.add(f"{int(a):04d}-{mois:02d}-{int(j):02d}")
    return trouvees


def date_concordante(person: PersonFacts, rec: dict) -> bool:
    """Le titre porte-t-il une date complète égale à la naissance ou au décès ?

    C'est le SEUL moyen pour une piste Gallica d'atteindre « forte » : le titre
    ne fournissant qu'un facteur (voir `pistes_gallica`), il en faut un second,
    et seule une date complète en est un. En pratique un titre de presse en
    porte rarement une — c'est assumé : la presse contextualise, elle n'identifie pas.
    """
    du_titre = dates_du_texte(rec.get("title", ""))
    if not du_titre:
        return False
    attendues = {event_iso(person.birth), event_iso(person.death)}
    return bool(du_titre & {d for d in attendues if len(d) == 10})


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
        # Le titre est UNE preuve, pas deux. `nom` et `lieu` en sont tous deux
        # extraits : les compter séparément ferait basculer « Le Journal de
        # Montbéliard » en piste FORTE pour un Dupont né à Montbéliard — donc
        # écrite dans l'arbre — sans qu'aucune identité n'ait été vérifiée.
        # Le titre ne contribue donc qu'un seul facteur ; seule une date
        # complète concordante peut en apporter un second.
        # Comparaison par MOTS ENTIERS, jamais par sous-chaîne (« Roy »/« LEROY »).
        concordances: list[str] = []
        mots_titre = mots(rec.get("title", ""))
        if mots(person.surname) and mots(person.surname) <= mots_titre:
            concordances.append("nom")
        elif lieu_arbre and mots(lieu_arbre) <= mots_titre:
            concordances.append("lieu")
        if date_concordante(person, rec):
            concordances.append("date complète")
        pistes.append(Piste(
            gramps_id=person.gramps_id, handle=person.handle,
            source="gallica", identite=identite, identite_derivee=False,
            url=rec.get("url") or None,
            requete=requete,
            concordances=concordances, divergences=[],
        ))
    return pistes
