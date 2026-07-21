"""Détection des doublons de lieux : candidats, preuve, survivant. Pur, sans réseau.

Pendant de `duplicates.py`, qui fait le même travail pour les personnes, avec une
différence décisive : une commune possède un **identifiant canonique** — son code
officiel — que les personnes n'ont pas. La preuve y est donc plus forte et plus
simple à énoncer. La doctrine, elle, ne change pas : la ressemblance ne prouve
jamais l'identité (ADR 0013).
"""

from __future__ import annotations

import re
import unicodedata

from crewai_custom_tools.tools.genealogy.models.domain import PlaceFacts

__all__ = ["evaluer_preuve", "normaliser_nom_lieu"]

# Les ligatures ne sont pas des accents : NFD ne les décompose pas. « Vœuil-et-Giget »
# et « Voeuil-et-Giget » désignent pourtant la même commune de Charente. Cette table
# se limite aux ligatures ; les lettres barrées (ø/Ø danois, ł polonais, đ croate…)
# n'en sont pas — ce sont des lettres à part entière, distinctes d'un accent ou d'une
# ligature composée — et restent délibérément hors champ.
_LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})

# L'apostrophe typographique ’ (U+2019) est l'usage standard et arrive par
# copier-coller ; elle rejoint la classe des séparateurs plutôt que d'être
# supprimée — sinon « L'Isle-Adam » se confondrait avec « Lisle-Adam ».
_SEPARATEURS = re.compile(r"[\s\-'’]+")


def normaliser_nom_lieu(nom: str) -> str:
    """Nom de lieu → clé de comparaison : sans accents, minuscule, séparateurs unifiés."""
    deplie = (nom or "").translate(_LIGATURES)
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", deplie)
        if unicodedata.category(c) != "Mn")
    return _SEPARATEURS.sub(" ", sans_accents).strip().lower()


PREUVE_CODE = "code"
PREUVE_COORDONNEES = "coordonnees"


def evaluer_preuve(a: PlaceFacts, b: PlaceFacts) -> str:
    """La preuve qui autorise une fusion automatique, ou la chaîne vide. Pur.

    Un VETO passe avant tout : deux codes non vides et différents interdisent la
    fusion, quels que soient les types et les coordonnées. C'est lui qui protège
    Paris — le département 75 et la commune 75056 sont deux entités réelles.

    Hors veto, deux voies :
      - codes identiques et non vides : un code officiel est canonique, il prouve
        quel que soit le type des deux lieux ;
      - même type ET coordonnées complètes identiques : la voie des lieux sans
        code. Les coordonnées ne prouvent JAMAIS rien entre types différents —
        un département géocodé reçoit le point de sa préfecture, c'est-à-dire
        celui de sa commune-chef-lieu.
    """
    if a.code and b.code and a.code != b.code:
        return ""
    if a.code and b.code:                       # égaux, et non vides : canonique
        return PREUVE_CODE
    if a.place_type != b.place_type:
        return ""
    if a.lat and a.long and (a.lat, a.long) == (b.lat, b.long):
        return PREUVE_COORDONNEES
    return ""
