"""Traduction « résultat d'archive → Piste ». Une fonction pure par source."""

from crewai_custom_tools.tools.genealogy.pistes.dhs import pistes_dhs
from crewai_custom_tools.tools.genealogy.pistes.gallica import (
    ark_de,
    date_concordante,
    dates_du_texte,
    fenetre_vie,
    personne_eligible,
    pistes_gallica,
    requete_gallica,
)
from crewai_custom_tools.tools.genealogy.pistes.matchid import (
    event_iso,
    first_given,
    norm_nom,
    pistes_matchid,
)
from crewai_custom_tools.tools.genealogy.pistes.wikidata import (
    mots,
    pistes_wikidata,
    q_item,
    requete_wikidata,
)

__all__ = [
    "ark_de",
    "date_concordante",
    "dates_du_texte",
    "event_iso",
    "fenetre_vie",
    "first_given",
    "mots",
    "norm_nom",
    "personne_eligible",
    "pistes_dhs",
    "pistes_gallica",
    "pistes_matchid",
    "pistes_wikidata",
    "q_item",
    "requete_gallica",
    "requete_wikidata",
]
