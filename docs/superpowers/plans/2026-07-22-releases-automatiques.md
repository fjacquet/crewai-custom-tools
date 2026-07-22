# Plan d'implémentation — création automatique des GitHub Releases

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le push d'un tag `v*` publie tout seul la GitHub Release, corps extrait de la section correspondante du `CHANGELOG.md`.

**Architecture:** Un extracteur pur (`scripts/extract_changelog.py`, stdlib seule, testé hors ligne) découpe `CHANGELOG.md` et rend soit le titre de release, soit le corps. Un workflow GitHub Actions déclenché sur `push: tags: ['v*']` vérifie que le tag concorde avec `pyproject.toml`, appelle l'extracteur deux fois, puis publie via `gh release create`. Aucune dépendance tierce, aucun `pip install` dans le workflow.

**Tech Stack:** Python 3.11+ (stdlib : `argparse`, `re`, `pathlib`, `tomllib`), pytest, GitHub Actions, `gh` CLI (préinstallé sur les runners `ubuntu-latest`).

**Spec de référence:** `docs/superpowers/specs/2026-07-22-releases-automatiques-design.md`

**Branche:** `chore/releases-automatiques` (déjà créée, la spec y est commitée en `23a149a`).

## Global Constraints

- **Python ≥ 3.11.** Le script n'importe **que la stdlib** — c'est ce qui permet au workflow de sauter l'installation des dépendances.
- **Ruff** : `line-length = 120`, `select = ["E", "W", "I", "UP", "B", "C4", "SIM", "RUF"]`. La CI lance `ruff check src tests` — `scripts/` n'est **pas** dans le périmètre du linter, mais `tests/` l'est : le fichier de test doit passer.
- **Tests 100 % hors ligne.** Aucun accès réseau, aucun appel à `gh` dans les tests.
- **`pythonpath = ["scripts"]`** est déjà configuré dans `[tool.pytest.ini_options]` : un test peut faire `import extract_changelog` directement, sans bricoler `sys.path`.
- **Langue** : docstrings, commentaires et messages de commit en français, comme le reste du dépôt. Les mots-clés de commit (`feat`, `fix`, `chore`, `docs`, `ci`) restent en anglais.
- **`python` nu n'est pas sur le PATH en local.** Lancer les tests avec `uv run python -m pytest` (et non `uv run pytest`, intercepté par le proxy rtk).
- **Ne pas toucher** à `__version__`, à `version` dans `pyproject.toml`, ni au numéro de version courant : ce plan ne publie aucune version nouvelle, il rattrape trois releases manquantes.

---

## Task 1 : l'extracteur de CHANGELOG

**Files:**
- Create: `scripts/extract_changelog.py`
- Test: `tests/test_extract_changelog.py`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces:
  - `normaliser_version(brut: str) -> str` — `"v0.28.0"` et `"0.28.0"` rendent tous deux `"0.28.0"`.
  - `extraire(texte: str, version: str) -> tuple[str, str]` — rend `(titre_release, corps)`. Lève `KeyError(version)` si la section est absente.
  - `main(argv: list[str] | None = None) -> int` — code de sortie, `0` en succès et `1` en échec.
  - CLI : `python scripts/extract_changelog.py <version|tag> [--titre] [--fichier CHEMIN]`.
  - Constantes `RACINE` et `CHANGELOG_PAR_DEFAUT` (`pathlib.Path`), utilisées par la Task 2.

---

- [ ] **Step 1 : écrire les tests qui échouent**

Créer `tests/test_extract_changelog.py` :

```python
"""Tests de `scripts/extract_changelog.py` — découpage de CHANGELOG.md.

Le fichier fixture reproduit les trois formes réelles du CHANGELOG du dépôt :
une section avec descriptif dans le heading, une section sans descriptif et
sans séparateur `---` de fin (le cas de 0.21.1, 0.19.1, 0.2.0 et 0.1.0), et
une dernière section bornée par la fin du fichier.
"""

import pytest

from extract_changelog import RACINE, extraire, main, normaliser_version

CHANGELOG = """\
# Changelog

Prose d'introduction.

---

## [0.28.0] - 2026-07-22 — Fusion des lieux

### Added

- Le détecteur de doublons.

---

## [0.27.0] - 2026-07-22

### Changed

- Configuration de ruff.

## [0.26.0] - 2026-07-21

### Added

- Champs structurés.
"""


def test_titre_reprend_le_descriptif_du_heading():
    titre, _ = extraire(CHANGELOG, "0.28.0")
    assert titre == "v0.28.0 — Fusion des lieux"


def test_titre_retombe_sur_le_tag_sans_descriptif():
    titre, _ = extraire(CHANGELOG, "0.27.0")
    assert titre == "v0.27.0"


def test_corps_borne_par_la_section_suivante_et_separateur_retire():
    _, corps = extraire(CHANGELOG, "0.28.0")
    assert corps == "### Added\n\n- Le détecteur de doublons."


def test_corps_borne_sans_separateur_de_fin():
    _, corps = extraire(CHANGELOG, "0.27.0")
    assert corps == "### Changed\n\n- Configuration de ruff."


def test_derniere_section_bornee_par_la_fin_du_fichier():
    _, corps = extraire(CHANGELOG, "0.26.0")
    assert corps == "### Added\n\n- Champs structurés."


def test_version_absente_leve_key_error():
    with pytest.raises(KeyError):
        extraire(CHANGELOG, "9.9.9")


def test_tag_et_version_nue_designent_la_meme_section():
    assert normaliser_version("v0.28.0") == "0.28.0"
    assert normaliser_version("0.28.0") == "0.28.0"


def test_main_imprime_le_corps(tmp_path, capsys):
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(CHANGELOG, encoding="utf-8")
    code = main(["v0.28.0", "--fichier", str(fichier)])
    assert code == 0
    assert capsys.readouterr().out.strip() == "### Added\n\n- Le détecteur de doublons."


def test_main_imprime_le_titre(tmp_path, capsys):
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(CHANGELOG, encoding="utf-8")
    code = main(["v0.28.0", "--titre", "--fichier", str(fichier)])
    assert code == 0
    assert capsys.readouterr().out.strip() == "v0.28.0 — Fusion des lieux"


def test_main_echoue_bruyamment_si_la_version_est_absente(tmp_path, capsys):
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(CHANGELOG, encoding="utf-8")
    code = main(["v9.9.9", "--fichier", str(fichier)])
    assert code == 1
    capture = capsys.readouterr()  # une seule lecture : elle vide le tampon
    assert "9.9.9" in capture.err
    assert capture.out == ""


def test_le_changelog_reel_expose_la_version_courante():
    """Garde de non-régression : le vrai CHANGELOG reste lisible par le script.

    Elle attrape en CI, avant même que le tag soit posé, les deux pannes qui
    feraient rougir le workflow de release : une entrée CHANGELOG oubliée pour
    la version courante, ou un heading dont la forme a dérivé.
    """
    from crewai_custom_tools import __version__

    texte = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
    titre, corps = extraire(texte, __version__)
    assert titre.startswith(f"v{__version__}")
    assert corps.strip()
```

- [ ] **Step 2 : lancer les tests pour vérifier qu'ils échouent**

Run: `uv run python -m pytest tests/test_extract_changelog.py -q`
Expected: FAIL — collecte impossible, `ModuleNotFoundError: No module named 'extract_changelog'`.

- [ ] **Step 3 : écrire l'implémentation**

Créer `scripts/extract_changelog.py` :

```python
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

    print(titre if args.titre else corps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4 : lancer les tests pour vérifier qu'ils passent**

Run: `uv run python -m pytest tests/test_extract_changelog.py -q`
Expected: PASS — `11 passed`.

- [ ] **Step 5 : vérifier la suite complète et le linter**

Run: `uv run python -m pytest -q`
Expected: PASS — `1025 passed` (1014 avant, plus les 11 nouveaux).

Run: `uv run ruff check src tests`
Expected: `All checks passed!`

- [ ] **Step 6 : vérifier le script sur le CHANGELOG réel**

Run: `uv run python scripts/extract_changelog.py v0.27.0 --titre`
Expected: `v0.27.0` — sans descriptif, puisque le heading n'en a pas encore (il sera ajouté en Task 3).

Run: `uv run python scripts/extract_changelog.py v9.9.9; echo "code=$?"`
Expected: sur `stderr` `Aucune section « ## [9.9.9] » dans …/CHANGELOG.md`, puis `code=1`.

- [ ] **Step 7 : commit**

```bash
git add scripts/extract_changelog.py tests/test_extract_changelog.py
git commit -m "$(cat <<'EOF'
feat(release): extracteur de section de CHANGELOG

Découpe CHANGELOG.md et rend soit le titre de release, soit le corps de la
section. Stdlib seule, sans réseau ni appel à gh : le workflow qui l'appellera
n'a donc rien à installer, et la fonction est testable hors ligne comme le
reste de la suite.

Le descriptif du heading est optionnel — les 38 entrées existantes n'en ont
pas — et le séparateur `---` de fin de section n'est retiré que s'il est là :
il manque devant quatre des trente-sept frontières du fichier.

Un test lit le vrai CHANGELOG et exige que la version courante y ait une
section non vide. Il attrape en CI, avant que le tag soit posé, l'entrée
oubliée qui ferait rougir la publication.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 : le workflow de publication

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `CLAUDE.md:85`

**Interfaces:**
- Consumes: `scripts/extract_changelog.py` de la Task 1 — CLI `python scripts/extract_changelog.py <tag> [--titre]`, code de sortie non nul si la section manque.
- Produces: rien qu'une tâche ultérieure consomme.

---

- [ ] **Step 1 : écrire le workflow**

Créer `.github/workflows/release.yml`. Il suit les conventions de `ci.yml` (`actions/checkout@v7`, `actions/setup-python@v7`, Python 3.13) mais **n'installe aucune dépendance** — l'extracteur et `tomllib` sont dans la stdlib, et `gh` est préinstallé sur les runners `ubuntu-latest`.

```yaml
name: Release

on:
  push:
    tags: [ "v*" ]

permissions:
  contents: write

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v7

      - name: Setup Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.13"

      # tests/test_scaffold.py compare __version__ et pyproject.toml entre eux,
      # mais rien ne vérifie que le tag est posé sur le bon commit. C'est le
      # seul mode de panne qui reste, et il doit bloquer avant publication.
      - name: Verify Tag Matches Declared Version
        run: |
          set -euo pipefail
          declaree="v$(python -c 'import tomllib, pathlib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')"
          if [ "$GITHUB_REF_NAME" != "$declaree" ]; then
            echo "::error::Tag $GITHUB_REF_NAME, mais pyproject.toml déclare $declaree"
            exit 1
          fi

      # Sortie non nulle si la section manque : jamais de release au corps vide.
      - name: Extract Release Notes
        run: |
          set -euo pipefail
          python scripts/extract_changelog.py "$GITHUB_REF_NAME" --titre > "$RUNNER_TEMP/titre.txt"
          python scripts/extract_changelog.py "$GITHUB_REF_NAME" > "$RUNNER_TEMP/corps.md"

      - name: Publish Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          gh release create "$GITHUB_REF_NAME" \
            --verify-tag \
            --title "$(cat "$RUNNER_TEMP/titre.txt")" \
            --notes-file "$RUNNER_TEMP/corps.md"
```

Deux choix à ne pas défaire :
- Les fichiers intermédiaires vont dans `$RUNNER_TEMP`, pas dans l'arbre de travail — ils ne doivent pas se retrouver dans le dépôt checkouté.
- Pas de `--clobber` ni de `|| true` sur `gh release create`. Si la release existe déjà, le workflow doit rougir plutôt qu'écraser en silence un corps rédigé à la main.

- [ ] **Step 2 : vérifier la syntaxe YAML**

`pyyaml` 6.0.3 est déjà dans l'environnement (dépendance transitive), rien à installer.

Run:
```bash
uv run python -c "
import yaml, pathlib
d = yaml.safe_load(pathlib.Path('.github/workflows/release.yml').read_text())
print('cles:', list(d))
print('declencheur:', d[True])
"
```
Expected:
```
cles: ['name', True, 'permissions', 'jobs']
declencheur: {'push': {'tags': ['v*']}}
```

Le `True` n'est pas une coquille et n'est pas un bug : YAML 1.1 résout la clé nue `on` en booléen vrai, d'où l'accès par `d[True]`. GitHub Actions lit le fichier avec son propre parseur et n'est pas concerné.

- [ ] **Step 3 : simuler localement les deux commandes d'extraction du workflow**

Run:
```bash
uv run python scripts/extract_changelog.py v0.27.0 --titre
uv run python scripts/extract_changelog.py v0.27.0 | head -5
```
Expected: le titre `v0.27.0`, puis les cinq premières lignes de la section 0.27.0 du CHANGELOG, commençant par `### Changed`.

- [ ] **Step 4 : mettre à jour CLAUDE.md**

Remplacer la ligne 85 de `CLAUDE.md` :

```
- Releasing is not done until the tag exists: bump both versions → CHANGELOG entry → `git tag -a vX.Y.Z` → `gh release create`. Five versions shipped to `main` untagged before this was written.
```

par :

```
- Releasing: bump both versions → CHANGELOG entry, **with a descriptor in the heading** (`## [0.28.0] - 2026-07-22 — Fusion des lieux`) → `git tag -a vX.Y.Z` → `git push --tags`. `.github/workflows/release.yml` then publishes the GitHub Release on tag push, title and body extracted from that CHANGELOG section by `scripts/extract_changelog.py`. Do **not** run `gh release create` by hand — it collides with the workflow. Thirteen tags never got a release while this step was manual, which is why `v0.24.0` sat as "Latest" while the code said 0.27.0.
```

- [ ] **Step 5 : vérifier que rien n'a cassé**

Run: `uv run python -m pytest -q`
Expected: PASS — `1025 passed`.

- [ ] **Step 6 : commit**

```bash
git add .github/workflows/release.yml CLAUDE.md
git commit -m "$(cat <<'EOF'
ci(release): publier la GitHub Release au push d'un tag v*

L'étape `gh release create` était manuelle et sans garde-fou : treize tags sur
trente-neuf n'ont jamais donné lieu à une release, dont les trois derniers, et
la page affichait v0.24.0 en « Latest » pendant que le code annonçait 0.27.0.

Le workflow extrait titre et corps de la section CHANGELOG du tag, après avoir
vérifié que le tag concorde avec la version déclarée dans pyproject.toml — le
seul mode de panne que test_scaffold.py ne couvre pas, puisqu'il compare les
deux déclarations de version entre elles et jamais au tag.

Aucune dépendance installée : l'extracteur et tomllib sont dans la stdlib, gh
est préinstallé sur les runners.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 : rattrapage des trois releases manquantes

**Files:**
- Modify: `CHANGELOG.md` (trois lignes de heading : `## [0.27.0]`, `## [0.26.0]`, `## [0.25.0]`)

**Interfaces:**
- Consumes: `scripts/extract_changelog.py` de la Task 1.
- Produces: rien de logiciel — trois GitHub Releases publiées.

> **Action irréversible et publique.** Le Step 4 publie trois releases visibles de tous. Ne pas l'exécuter sans que l'humain ait relu les corps affichés au Step 3 et donné son accord explicite.

---

- [ ] **Step 1 : ajouter le descriptif aux trois headings**

Dans `CHANGELOG.md`, remplacer exactement ces trois lignes :

| Ligne actuelle | Remplacement |
|---|---|
| `## [0.27.0] - 2026-07-22` | `## [0.27.0] - 2026-07-22 — Configuration de ruff et mise en conformité` |
| `## [0.26.0] - 2026-07-22` | `## [0.26.0] - 2026-07-22 — Champs structurés sur PropositionAudit` |
| `## [0.25.0] - 2026-07-22` | `## [0.25.0] - 2026-07-22 — Référentiel des subdivisions administratives` |

Les descriptifs reprennent mot pour mot les messages de commit de release correspondants (`chore(release): 0.27.0 — configuration de ruff et mise en conformité`, etc.), casse initiale mise en majuscule.

Ne **pas** toucher aux 35 autres headings : la convention vaut pour la suite, pas rétroactivement.

- [ ] **Step 2 : vérifier que les descriptifs sont bien lus**

Run:
```bash
for v in 0.25.0 0.26.0 0.27.0; do uv run python scripts/extract_changelog.py "$v" --titre; done
```
Expected:
```
v0.25.0 — Référentiel des subdivisions administratives
v0.26.0 — Champs structurés sur PropositionAudit
v0.27.0 — Configuration de ruff et mise en conformité
```

Run: `uv run python -m pytest tests/test_extract_changelog.py -q`
Expected: PASS — `11 passed`. Le test `test_le_changelog_reel_expose_la_version_courante` valide au passage le nouveau heading de 0.27.0.

- [ ] **Step 3 : afficher les trois corps pour relecture humaine**

Run:
```bash
for v in 0.25.0 0.26.0 0.27.0; do
  echo "════════ v$v — $(uv run python scripts/extract_changelog.py "$v" --titre)"
  uv run python scripts/extract_changelog.py "$v"
  echo
done
```
Expected: les trois sections du CHANGELOG, sans le `---` de fin ni lignes vides de bord, et sans déborder sur la section voisine.

**Arrêt ici.** Présenter la sortie à l'humain et attendre son accord avant le Step 4.

- [ ] **Step 4 : publier les trois releases**

Les tags `v0.25.0`, `v0.26.0` et `v0.27.0` existent déjà sur `origin` — `gh` s'y attache sans rien créer côté git.

```bash
set -euo pipefail
corps=$(mktemp)
for v in 0.25.0 0.26.0 0.27.0; do
  uv run python scripts/extract_changelog.py "$v" > "$corps"
  gh release create "v$v" \
    --verify-tag \
    --title "$(uv run python scripts/extract_changelog.py "$v" --titre)" \
    --notes-file "$corps"
done
rm -f "$corps"
```

Un fichier temporaire réel plutôt qu'une substitution de processus : `gh` relit le descripteur, et un `/dev/fd` consommé donnerait un corps vide sans le moindre message d'erreur.

Expected: trois URL `https://github.com/fjacquet/crewai_custom_tools/releases/tag/v0.2X.0`.

Note : le corps est lu depuis le CHANGELOG de la branche courante, pas de celui figé dans le tag — les tags précèdent l'ajout des descriptifs. Sans conséquence : seul le heading change, le contenu des sections est identique.

- [ ] **Step 5 : vérifier l'état de la page Releases**

Run: `gh release list --limit 5`
Expected: `v0.27.0 — Configuration de ruff et mise en conformité` marqué `Latest`, suivi de `v0.26.0`, `v0.25.0`, `v0.24.0`, `v0.23.1`.

Run: `comm -23 <(git tag --sort=v:refname | sort) <(gh release list --limit 100 --json tagName -q '.[].tagName' | sort)`
Expected: exactement les dix vieux tags hors périmètre, et aucun des trois rattrapés :
```
v0.1.1
v0.19.2
v0.19.3
v0.20.0
v0.21.0
v0.21.1
v0.4.0
v0.5.0
v0.5.1
v0.6.0
```

- [ ] **Step 6 : commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs(changelog): descriptif dans les headings 0.25.0 à 0.27.0

Le workflow de release tire le titre de la Release du heading. Les trois
versions rattrapées reçoivent donc le descriptif de leur commit de release.

Les 35 headings antérieurs restent tels quels : la convention vaut pour la
suite, et le script sait lire les deux formes.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Vérification finale

- [ ] `uv run python -m pytest -q` → `1025 passed`
- [ ] `uv run ruff check src tests` → `All checks passed!`
- [ ] `gh release list --limit 3` → `v0.27.0` en `Latest`
- [ ] `git status --short` → vide
- [ ] Le workflow `release.yml` n'a **pas encore tourné** : il ne se déclenchera qu'au prochain push de tag. Sa première exécution réelle sera la version 0.28.0.
