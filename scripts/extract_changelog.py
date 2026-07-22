#!/usr/bin/env python3
"""Extrait une section de `CHANGELOG.md` : le corps d'une release, ou son titre.

Appelé par `.github/workflows/release.yml` au push d'un tag `v*`, et à la main
pour rattraper une release oubliée. Pure manipulation de texte : ni réseau, ni
appel à `gh`, stdlib seule — c'est ce qui permet au workflow de se passer
d'installer quoi que ce soit.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHANGELOG_PAR_DEFAUT = RACINE / "CHANGELOG.md"

# `## [0.28.0] - 2026-07-22` ou `## [0.28.0] - 2026-07-22 — Fusion des lieux`.
# Le descriptif est optionnel : les 38 entrées écrites avant cette convention
# n'en ont pas, et elles doivent rester lisibles par le script.
EN_TETE = re.compile(r"^## \[(?P<version>[^\]]+)\]\s+-\s+(?P<date>\S+)(?:\s+—\s+(?P<titre>.+?))?\s*$")


def normaliser_version(brut: str) -> str:
    """`v0.28.0` et `0.28.0` désignent la même section."""
    return brut[1:] if brut.startswith("v") else brut


def _sans_vides_de_bord(lignes: list[str]) -> list[str]:
    debut, fin = 0, len(lignes)
    while debut < fin and not lignes[debut].strip():
        debut += 1
    while fin > debut and not lignes[fin - 1].strip():
        fin -= 1
    return lignes[debut:fin]


def _nettoyer(lignes: list[str]) -> list[str]:
    """Retire les vides de bord, puis un séparateur `---` de fin s'il y en a un.

    Il y en a un devant 33 des 37 frontières du CHANGELOG, pas devant les
    quatre autres : son absence n'est pas une anomalie.
    """
    corps = _sans_vides_de_bord(lignes)
    if corps and corps[-1].strip() == "---":
        corps = _sans_vides_de_bord(corps[:-1])
    return corps


def extraire(texte: str, version: str) -> tuple[str, str]:
    """Rend `(titre_release, corps)` pour `version`. Lève `KeyError` si absente."""
    lignes = texte.splitlines()
    debut, descriptif = None, None
    for index, ligne in enumerate(lignes):
        entete = EN_TETE.match(ligne)
        if entete and entete.group("version") == version:
            debut, descriptif = index + 1, entete.group("titre")
            break
    if debut is None:
        raise KeyError(version)

    fin = next((i for i in range(debut, len(lignes)) if lignes[i].startswith("## [")), len(lignes))
    titre = f"v{version} — {descriptif}" if descriptif else f"v{version}"
    return titre, "\n".join(_nettoyer(lignes[debut:fin]))


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Extrait une section de CHANGELOG.md.")
    parseur.add_argument("version", help="numéro de version ou tag, par exemple 0.28.0 ou v0.28.0")
    parseur.add_argument(
        "--titre",
        action="store_true",
        help="imprimer le titre de release au lieu du corps de la section",
    )
    parseur.add_argument("--fichier", type=Path, default=CHANGELOG_PAR_DEFAUT)
    args = parseur.parse_args(argv)

    version = normaliser_version(args.version)
    try:
        texte = args.fichier.read_text(encoding="utf-8")
    except OSError as erreur:
        print(f"CHANGELOG illisible : {erreur}", file=sys.stderr)
        return 1
    try:
        titre, corps = extraire(texte, version)
    except KeyError:
        print(f"Aucune section « ## [{version}] » dans {args.fichier}", file=sys.stderr)
        return 1

    if not corps.strip():
        print(f"Section « ## [{version}] » vide dans {args.fichier}", file=sys.stderr)
        return 1

    print(titre if args.titre else corps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
