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

__all__ = [
    "PREUVE_CODE",
    "PREUVE_COORDONNEES",
    "evaluer_preuve",
    "normaliser_nom_lieu",
]

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

# Les deux orthographes de l'ignorance. Le modèle `PlaceFacts` laisse `place_type`
# à `""` par défaut, tandis que l'API Gramps rend le libellé `"Unknown"` — cf.
# `genecrew/places_apply.py`, qui teste `(place.get("place_type") or "Unknown")
# != "Unknown"`. Les deux désignent le même état : on ne sait pas. Faire dépendre
# un verdict de fusion de l'orthographe rendue serait un pur hasard.
_TYPES_INCONNUS = frozenset({"", "unknown"})


def _renseigne(champ: str) -> str:
    """Champ libre de l'API → sa valeur utile, ou `""` s'il ne porte que des blancs.

    `code`, `lat` et `long` sont des chaînes saisies à la main dans Gramps. Un
    champ « vidé » en y tapant une espace reste truthy en Python : sans ce
    nettoyage, deux `" "` se prouveraient mutuellement comme un code canonique.
    """
    return (champ or "").strip()


def _type_connu(place: PlaceFacts) -> str:
    """Type du lieu s'il est connu, sinon `""` — l'ignorance n'est pas une valeur."""
    brut = _renseigne(place.place_type)
    return "" if brut.casefold() in _TYPES_INCONNUS else brut


def evaluer_preuve(a: PlaceFacts, b: PlaceFacts) -> str:
    """La preuve qui autorise une fusion automatique, ou la chaîne vide. Pur.

    Un VETO passe avant tout : deux codes non vides et différents interdisent la
    fusion, quels que soient les types et les coordonnées. C'est lui qui protège
    Paris — le département 75 et la commune 75056 sont deux entités réelles.

    Hors veto, deux voies :
      - codes identiques et non vides : un code officiel est canonique, il prouve
        quel que soit le type des deux lieux ;
      - deux types CONNUS et égaux ET coordonnées complètes identiques : la voie
        des lieux sans code. Les coordonnées ne prouvent JAMAIS rien entre types
        différents — un département géocodé reçoit le point de sa préfecture,
        c'est-à-dire celui de sa commune-chef-lieu — ni dès qu'un seul des deux
        types est inconnu : un inconnu n'est jamais égal à un autre inconnu.
        C'est la doctrine du module jumeau `duplicates.py`, qui exige un nom
        « identique et non vide » et refuse dès qu'un parent est inconnu. Sans
        elle, un arrondissement « Bourges » encore `Unknown` mais géocodé au
        point de son chef-lieu fusionnerait tout seul avec la commune du même
        nom — l'état sans type étant l'état majoritaire de l'arbre réel.

    Fonction symétrique : `evaluer_preuve(a, b) == evaluer_preuve(b, a)`. Une
    écriture irréversible ne doit pas dépendre de l'ordre de parcours.
    """
    code_a, code_b = _renseigne(a.code), _renseigne(b.code)
    if code_a and code_b:
        return PREUVE_CODE if code_a == code_b else ""
    type_a, type_b = _type_connu(a), _type_connu(b)
    if not type_a or not type_b or type_a != type_b:
        return ""
    coord_a = (_renseigne(a.lat), _renseigne(a.long))
    if all(coord_a) and coord_a == (_renseigne(b.lat), _renseigne(b.long)):
        return PREUVE_COORDONNEES
    return ""
