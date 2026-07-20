"""MatchID (INSEE décès) → Piste. Pure : n'écrit rien, ne conclut rien."""

import unicodedata

from crewai_custom_tools.tools.genealogy.models.domain import EventFact, PersonFacts, Piste


def norm_nom(valeur: str) -> str:
    """Sans accents, sans espaces de bord, en majuscules. Partagé par les sources."""
    sans = "".join(c for c in unicodedata.normalize("NFD", valeur or "")
                   if unicodedata.category(c) != "Mn")
    return sans.strip().upper()


def event_iso(event: EventFact | None) -> str:
    """"AAAA-MM-JJ" si la date est complète, "AAAA" si l'année est seule, "" sinon.

    La LONGUEUR distingue les deux cas, et c'est ce qui empêche une année seule de
    compter comme facteur de concordance : règle projet, une année n'est jamais
    discriminante (trop d'homonymes naissent la même année).

    Fonction partagée : `genecrew.deces` l'importe d'ici plutôt que d'en garder
    une copie locale, pour ne jamais désynchroniser les deux définitions.
    """
    if event is None or not event.year:
        return ""
    dv = event.dateval or []
    if len(dv) >= 3 and dv[0] and dv[1]:
        return f"{dv[2]:04d}-{dv[1]:02d}-{dv[0]:02d}"
    return f"{event.year:04d}"


def first_given(given: str) -> str:
    """Premier prénom, virgules de l'arbre retirées ('Paul, Marcel' -> 'Paul'). Pure.

    MatchID répond 422 sur 'Paul,'. Fonction partagée : voir `event_iso` ci-dessus.
    """
    return (given.replace(",", " ").split() or [""])[0]


def pistes_matchid(person: PersonFacts, match: dict, url: str) -> Piste:
    """Transforme un résultat MatchID en piste. N'écrit rien, ne conclut rien.

    L'année de naissance seule ne compte PAS comme facteur : il faut une date
    complète (jour + mois + année) pour constituer un second facteur à côté du nom.
    """
    concordances: list[str] = []
    divergences: list[str] = []
    nom_insee = (match.get("name") or {}).get("last", "")
    if nom_insee and norm_nom(nom_insee) == norm_nom(person.surname):
        concordances.append("nom")
    naissance_insee = ((match.get("birth") or {}).get("date") or "")
    naissance_arbre = event_iso(person.birth)
    if len(naissance_insee) == 8 and len(naissance_arbre) == 10:
        iso_insee = f"{naissance_insee[:4]}-{naissance_insee[4:6]}-{naissance_insee[6:]}"
        if iso_insee == naissance_arbre:
            concordances.append("date complète")
        else:
            divergences.append("dates de naissance différentes")
    return Piste(
        gramps_id=person.gramps_id, handle=person.handle,
        source="matchid", identite=str(match.get("id") or ""),
        url=url or None,
        requete=f"nom={person.surname}&prenom={first_given(person.given)}",
        concordances=concordances, divergences=divergences,
    )
