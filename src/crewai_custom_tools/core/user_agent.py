"""User-Agent conforme à la politique Wikimedia : nom, version ET moyen de contact.

Wikimedia demande qu'un client automatisé soit joignable, et l'exige d'autant plus pour
un usage soutenu. Une mise en conformité, donc — **pas** un correctif d'étranglement : la
mesure montre qu'une requête isolée revient en `200` avec ou sans contact dans l'en-tête,
et que le 429 se déclenche sur le volume. Ce que le contact change pour un client qui
télécharge des centaines de fichiers n'a pas été mesuré et n'est pas promis ici.

Un seul point de définition : une chaîne de conformité dupliquée dérive, et la moitié
des appels finirait anonyme sans que rien ne le signale.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

CONTACT = "https://github.com/fjacquet/crewai-custom-tools"


def user_agent(usage: str) -> str:
    """En-tête du format recommandé : `nom/version (contact; usage) bibliothèque`.

    `usage` distingue les appels dans les journaux d'un opérateur qui nous verrait passer
    ('place enrichment', 'media import') — c'est la moitié utile d'un contact.
    """
    try:
        v = version("crewai-custom-tools")
    except PackageNotFoundError:  # arbre de travail non installé : la version importe peu
        v = "dev"
    return f"crewai-custom-tools/{v} ({CONTACT}; {usage}) python-requests"
