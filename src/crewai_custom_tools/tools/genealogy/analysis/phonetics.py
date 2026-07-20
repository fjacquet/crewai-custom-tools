"""Clé phonétique française d'un patronyme — pure, stdlib only.

Sert UNIQUEMENT au rappel : elle regroupe des candidats à examiner, elle ne prouve
jamais une identité (spec §3.1). Ses limites sont assumées — elle rapproche les
graphies partageant la même ossature consonantique, pas les variations de voyelle
interne (`Lelevre` ne rejoint pas `Lelièvre`).
"""

from __future__ import annotations

import unicodedata


def normalize_name(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace.

    Déplacée depuis `duplicates.py`, qui la réexporte : `phonetics` ne doit
    dépendre de rien, sans quoi l'import de `cle_phonetique` par `duplicates`
    formerait un cycle.
    """
    decomposed = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(ascii_only.lower().split())


# Ordre significatif : "ch" est neutralisé en "x" AVANT que "c" ne devienne "k",
# faute de quoi Schneider deviendrait "skneider".
_REMPLACEMENTS = [
    ("ph", "f"),
    ("ch", "x"),
    ("qu", "k"),
    ("gu", "g"),
    ("c", "k"),
    ("y", "i"),
]

_TERMINAISONS_MUETTES = ("e", "s", "t", "d", "x", "z")

_LONGUEUR_MINIMALE = 2
"""On ne rabote jamais en deçà : "Est" ne doit pas se réduire à la chaîne vide."""


def cle_phonetique(nom: str) -> str:
    """Rend la clé phonétique d'un patronyme, ou la chaîne vide s'il est inexploitable."""
    lettres = "".join(c for c in normalize_name(nom) if c.isalpha())
    if not lettres:
        return ""
    for avant, apres in _REMPLACEMENTS:
        lettres = lettres.replace(avant, apres)
    deduplique: list[str] = []
    for caractere in lettres:
        if not deduplique or deduplique[-1] != caractere:
            deduplique.append(caractere)
    cle = "".join(deduplique)
    while len(cle) > _LONGUEUR_MINIMALE and cle[-1] in _TERMINAISONS_MUETTES:
        cle = cle[:-1]
    return cle
