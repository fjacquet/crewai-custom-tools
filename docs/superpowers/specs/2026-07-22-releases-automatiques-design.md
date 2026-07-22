# Spécification : création automatique des GitHub Releases

**Date** : 2026-07-22
**Statut** : APPROUVÉ / PRÊT POUR LE PLAN D'IMPLÉMENTATION

---

## 1. Problème

Le dépôt porte 39 tags, tous poussés sur `origin`, mais seulement 26 GitHub Releases. Treize tags
n'ont jamais donné lieu à une release, dont les trois plus récents : `v0.25.0`, `v0.26.0`,
`v0.27.0`. La page Releases affiche donc `v0.24.0` en « Latest » alors que le code, le
`CHANGELOG.md`, `pyproject.toml` et `__init__.py` annoncent tous 0.27.0 — cohérents entre eux.

Aucune divergence de version : l'objet *Release* manque, voilà tout. CLAUDE.md décrit pourtant le
rituel (« bump ×2 → CHANGELOG → `git tag -a` → `gh release create` ») ; c'est la dernière étape,
manuelle et sans garde-fou, qui saute. Elle a sauté treize fois.

Tags orphelins recensés : `v0.1.1`, `v0.4.0`, `v0.5.0`, `v0.5.1`, `v0.6.0`, `v0.19.2`, `v0.19.3`,
`v0.20.0`, `v0.21.0`, `v0.21.1`, `v0.25.0`, `v0.26.0`, `v0.27.0`.

---

## 2. Décision

Supprimer l'étape manuelle : le **push d'un tag `v*` crée et publie la Release**, corps extrait de
la section correspondante du `CHANGELOG.md`.

### Conséquence assumée sur le style

Les releases existantes ne sont **pas** une copie du CHANGELOG. Le corps de `v0.24.0` est un texte
réécrit — sections « La doctrine », « Une seule passe », « Tests » — de 2 746 caractères, distinct
des puces du CHANGELOG. La publication automatique met fin à cette réécriture : le corps *sera* la
section du CHANGELOG. Arbitrage accepté — un CHANGELOG déjà dense contre une prose supplémentaire
qu'on oublie d'écrire une fois sur deux.

### Alternatives écartées

| Option | Verdict |
|---|---|
| Release en **brouillon** préremplie, publiée à la main après enrichissement | Rejetée. Conserve le style narratif mais réintroduit une étape manuelle — celle-là même qui a échoué treize fois. |
| **Garde-fou seul** : un job qui échoue si un tag poussé n'a pas de release | Rejetée. Signale l'oubli sans le corriger ; le travail manuel reste entier. |
| `awk`/`sed` **inline** dans le YAML du workflow | Rejetée. Intestable, et le quoting sur tirets cadratins et accents est fragile — le dépôt est francophone. |
| **Action tierce** (`changelog-reader-action` et consorts) | Rejetée. Dépendance externe sur un chemin qui publie. |

---

## 3. Architecture

Deux composants, une frontière nette : un extracteur pur, sans réseau ni connaissance de GitHub, et
un workflow qui l'appelle et publie.

```
push tag v0.28.0
      |
      v
.github/workflows/release.yml
      |
      +-- garde : version(pyproject.toml) == tag ?   -- non --> échec bruyant
      |
      +-- scripts/extract_changelog.py 0.28.0 --titre  --> "v0.28.0 — Fusion des lieux"
      +-- scripts/extract_changelog.py 0.28.0          --> corps.md
      |
      v
gh release create v0.28.0 --title "..." --notes-file corps.md
```

### 3.1 `scripts/extract_changelog.py`

Fonction pure sur du texte : lit `CHANGELOG.md`, rend un titre ou un corps. Aucune E/S réseau,
aucun appel `gh`, stdlib seule — testable hors ligne comme le reste de la suite, et réutilisable en
local pour le rattrapage de la section 5.

**Interface**

```
python scripts/extract_changelog.py <version|tag> [--titre] [--fichier CHANGELOG.md]
```

- `<version|tag>` accepte `0.28.0` comme `v0.28.0` — le préfixe `v` est retiré avant recherche.
- Sans `--titre` : imprime le **corps** de la section sur la sortie standard.
- Avec `--titre` : imprime le **titre de release**, `v0.28.0 — Fusion des lieux`.
- `--fichier` : chemin du CHANGELOG. Par défaut `Path(__file__).resolve().parent.parent /
  "CHANGELOG.md"` — la racine du dépôt déduite de l'emplacement du script, comme le fait déjà
  `scripts/generate_sbom.py:99`, pour que l'appel marche depuis n'importe quel répertoire courant.
  Le flag existe pour les tests, qui écrivent leurs fixtures en `tmp_path`.

**Grammaire du heading**

```
## [VERSION] - DATE
## [VERSION] - DATE — TITRE
```

Le descriptif est **optionnel** : les 38 entrées actuelles n'en ont pas, et elles doivent rester
lisibles par le script. Le séparateur reconnu est le tiret cadratin `—`, conformément à ce
qu'écrivent déjà les messages de commit de release. Sans descriptif, le titre de release retombe
sur le seul nom du tag, `v0.28.0`.

**Bornes du corps**

Le corps court de la ligne qui suit le heading jusqu'à la prochaine ligne commençant par `## [`,
ou jusqu'à la fin du fichier pour la dernière section. Un séparateur `---` en fin de section est
retiré **s'il est présent** — il l'est devant 33 des 37 frontières du fichier, pas devant les
quatre autres (`0.21.1`, `0.19.1`, `0.2.0`, `0.1.0`). Son absence n'est donc pas une anomalie et ne
doit rien casser. Les lignes vides de bord sont retirées dans les deux cas.

**Panne**

Deux cas font échouer le script, tous deux avec message sur `stderr` et code de sortie non nul :
version introuvable, **et** section présente mais vide (le heading ajouté avant que son contenu
soit écrit). Jamais de release au corps vide : un CHANGELOG oublié — ou pas encore rempli — doit
faire rougir le workflow, pas publier une page blanche.

### 3.2 `.github/workflows/release.yml`

- Déclencheur : `on: push: tags: ['v*']`.
- `permissions: contents: write` — le strict nécessaire pour créer une release.
- `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` pour `gh`, préinstallé sur les runners `ubuntu-latest`.

Étapes :

1. **checkout** au tag. Le CHANGELOG lu est donc celui figé dans le tag, pas celui de `main` —
   c'est la propriété voulue : la release décrit ce que le tag contient.
2. **Garde de cohérence** : la `version` de `pyproject.toml` doit égaler le tag privé de son `v`.
   Elle attrape le seul mode de panne que `tests/test_scaffold.py` ne couvre pas — ce test compare
   `__version__` et `pyproject.toml` entre eux, mais rien ne vérifie que le tag est posé sur le bon
   commit. Divergence → échec avant toute publication.
3. **Extraction** du titre et du corps.
4. **Publication** : `gh release create "$TAG" --title "$TITRE" --notes-file corps.md`.

Si la release existe déjà, `gh` échoue et le workflow rougit. Un échec bruyant sur un cas rare vaut
mieux qu'un `--clobber` silencieux qui pourrait écraser un corps réécrit à la main.

---

## 4. Tests

`tests/test_extract_changelog.py`, hors ligne, fixtures écrites en `tmp_path`, assertions sur les
valeurs rendues :

| Cas | Attendu |
|---|---|
| Heading **avec** descriptif | Titre `v0.28.0 — Fusion des lieux`, corps de la section |
| Heading **sans** descriptif (les 38 entrées actuelles) | Titre `v0.28.0`, corps de la section |
| Section suivie d'une autre, **avec** `---` de fin | Le corps s'arrête au `## [` suivant ; `---` retiré |
| Section suivie d'une autre, **sans** `---` de fin | Le corps s'arrête au `## [` suivant ; dernière ligne de contenu préservée |
| **Dernière** section du fichier | Le corps court jusqu'à EOF, sans déborder |
| Version absente du CHANGELOG | Sortie non nulle, message explicite sur `stderr` |
| Section présente mais **vide** | Sortie non nulle : un heading ajouté sans contenu ne publie pas de page blanche |
| Argument `v0.28.0` vs `0.28.0` | Résultat identique |

Le workflow lui-même n'est pas testé en CI — il n'est vérifiable qu'à l'exécution. Le rattrapage de
la section 5 en fait la première validation réelle, sur trois versions.

---

## 5. Rattrapage

Manuel, en local, une fois. Trois versions seulement : `v0.25.0`, `v0.26.0`, `v0.27.0`.

1. Ajouter le descriptif aux trois headings du `CHANGELOG.md` :
   - `## [0.25.0] - 2026-07-22 — Référentiel des subdivisions administratives`
   - `## [0.26.0] - 2026-07-22 — Champs structurés sur PropositionAudit`
   - `## [0.27.0] - 2026-07-22 — Configuration de ruff et mise en conformité`
2. Pour chacune : `scripts/extract_changelog.py` puis `gh release create`.
3. « Latest » redevient `v0.27.0`.

Les 35 autres headings ne sont **pas** réécrits : la convention vaut pour la suite. Les dix vieux
tags orphelins (`v0.1.1` → `v0.21.1`) restent sans release — hors périmètre, aucune valeur à
reconstituer un historique que personne ne consulte.

Note : les tags `v0.25.0` à `v0.27.0` pointent sur des commits antérieurs à l'ajout des descriptifs.
Le rattrapage lit donc le CHANGELOG de la branche courante, pas celui du tag. Sans importance ici —
le contenu des sections est identique, seul le heading change.

---

## 6. Documentation

`CLAUDE.md`, section « Documentation & decisions » — le rituel de release perd une étape et en
gagne une contrainte :

> bump `__version__` **et** `version` → entrée CHANGELOG, **descriptif dans le heading** →
> `git tag -a vX.Y.Z` → `git push --tags`. La Release se crée toute seule.

Pas d'ADR. La décision porte sur le processus de publication, pas sur l'architecture du paquet, du
serveur MCP, de l'authentification ni du déploiement — les quatre domaines que couvrent les ADR
existants.

---

## 7. Hors périmètre

- Publication sur PyPI. Le workflow crée une Release GitHub, rien de plus.
- Réécriture des 35 headings de CHANGELOG existants.
- Releases pour les dix tags orphelins antérieurs à `v0.25.0`.
- Génération automatique du CHANGELOG lui-même : il est écrit à la main, et c'est voulu.
