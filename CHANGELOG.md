# Changelog

All notable changes to the `crewai-custom-tools` project will be documented in this file.

---

## [0.27.0] - 2026-07-22

### Changed

- **Configuration de ruff** — le dépôt tournait sur le jeu de règles **par défaut** (`E4`, `E7`,
  `E9`, `F`) : ni tri d'imports, ni longueur de ligne, ni fermeture sur variable de boucle, ni
  `zip` qui tronque en silence. Le linter passait au vert sur 730 signalements qu'il ne regardait
  pas. `select = ["E", "W", "I", "UP", "B", "C4", "SIM", "RUF"]`, `line-length = 120`.
  `RUF001`/`RUF002`/`RUF003` sont désactivées : projet francophone, l'apostrophe typographique et
  l'espace insécable sont voulues.
- 387 signalements corrigés, dont 246 automatiquement. `ruff check` rend désormais zéro.

### Fixed

- **`zip()` sans `strict=`** (3 occurrences, dont `genealogy/militaires.py`). Un `zip` sur deux
  séquences de longueurs différentes **tronque en silence**. Les trois invariants de longueur ont
  été vérifiés comme tenant par construction, puis explicités par `strict=True` — ce qui les fait
  respecter au lieu de les supposer.
- Attributs de classe mutables partagés entre instances (`RUF012`), variables dépaquetées ignorées
  par erreur (`RUF059`), imports `typing` dépréciés (`UP035`), `try/except/pass` remplacés par
  `contextlib.suppress` (`SIM105`).

### Notes

- `gramps_generated.py` est exempté d'`E501` par `per-file-ignores` plutôt que retouché : c'est un
  fichier généré, en-tête « NE PAS ÉDITER » (ADR 0004).
- `__all__` est exempté de `RUF022` : le tri alphabétique détruirait le regroupement volontaire par
  catégorie.

---

## [0.26.0] - 2026-07-22

### Added

- `PropositionAudit` gagne `date_iso` et `lieu_nom` — la donnée machine à côté de la phrase
  française, pour qu'une commande d'application n'ait jamais à re-parser de la prose. Requis par
  la cible `apply deaths` de genecrew.

---

## [0.25.0] - 2026-07-22

### Added

- **Référentiel des subdivisions administratives** — paquet `genealogy/referentiel/`, qui résout
  depuis Wikidata les subdivisions d'un pays (coordonnées, QID, article Wikipédia) pour qu'un arbre
  Gramps ait des contenants identifiés où rattacher ses communes. Neuf pays configurés : FR, IT, BE,
  CH, DE, US, DZ, PL, SY.
  - `config.py` — une ligne par pays : préfixe ISO, QID, langue du nom vernaculaire, types Gramps
    par niveau. **Types natifs uniquement** : un type personnalisé est une ligne de plus à ne pas
    oublier dans chaque filtre par type, avec un rattachement muet au bout.
  - `wikidata.py` — sélection par **code ISO 3166-2 (`P300`)**, jamais par classe `P31` : mesuré, la
    classe `provincia` rate Naples et Milan, qui sont des *villes métropolitaines*. Le mapper est
    pur et testé hors ligne sur des **charges Wikidata réelles figées**.
  - Le **niveau vient du rattachement `P131`**, jamais de la forme du code — en France les régions
    sont alphabétiques et les départements numériques, en Italie c'est l'inverse.
  - **Ancre pays** : les régions françaises pendent sous `Q212429` *France métropolitaine*, qui n'a
    pas de code ISO. Sans ancre, 12 entités françaises survivaient sur 125, toutes ultramarines. La
    requête demande donc si le pays est atteignable en un à trois sauts de `P131` — pas quatre, à
    quatre elle repêche du bruit.
  - **Rien n'est écarté en silence** : le mapper rend trois listes — retenues, collisions, et
    écartées avec leur motif. C'est l'absence de ce troisième canal qui avait masqué le défaut
    ci-dessus.
  - `chargement.py` — transport temporisé avec reprises. Un pays qui échoue après reprises est
    *signalé*, jamais fatal : les autres sont livrés.
- `Subdivision`, `CollisionIso` et `EntiteEcartee` (`models/domain.py`).

### Fixed

- **Le canton suisse prend le type Gramps natif `State`** au lieu du type personnalisé `Canton`.
- **`parse_pname` reconnaît un nom sans virgule suffixé d'un code cantonal** — `Montreux (VD)`.
  Sans cette règle, le pays restait vide, `resolve_ch` n'était **jamais appelé**, et le géocodeur
  mondial de repli rendait une hiérarchie sans canton. Dix-neuf lieux d'un arbre réel étaient dans
  ce cas. La garde « sans virgule » est délibérée : `(XX)` en suffixe existe ailleurs, et `GE`,
  `BE`, `JU` sont des chaînes courtes.
- **`DEFAULT_RATE_LIMITS` gagne une entrée `Wikidata`** — le nom de fournisseur était déjà employé
  sans qu'aucune limite ne lui corresponde, donc le limiteur n'y freinait rien.

> Note de publication : ce travail était présent dans `main` avant le tag `v0.24.0`, mais celui-ci
> pointe sur un commit antérieur à sa fusion et ne le contient pas.

---

## [0.24.0] - 2026-07-22

### Added

- **Détection des doublons de lieux** — `analysis/place_duplicates.py`, pur et testé hors ligne.
  Pendant du détecteur de doublons de personnes, avec une différence décisive : une commune possède
  un **identifiant canonique** (son code officiel) que les personnes n'ont pas, ce qui rend la preuve
  plus forte et plus simple à énoncer. La doctrine, elle, ne change pas (ADR 0013) : **la ressemblance
  ne prouve jamais l'identité**.
  - `normaliser_nom_lieu` — clé de comparaison : casse, accents, séparateurs, ligatures (`œ`, `æ`) et
    apostrophe typographique neutralisés. L'apostrophe reste un **séparateur** et non un caractère
    supprimé, sans quoi `L'Isle-Adam` se confondrait avec `Lisle-Adam`. Les lettres barrées (`ø`) sont
    délibérément hors périmètre, et un test verrouille cette frontière.
  - `evaluer_preuve` — **veto** d'abord : deux codes officiels renseignés et différents interdisent la
    fusion, quels que soient les types et les coordonnées. C'est lui qui protège le cas réel de Paris,
    présent en `Department` code 75 **et** en `Municipality` code 75056 — deux entités administratives
    distinctes. Hors veto, deux voies : codes identiques (canonique, vaut entre types différents), ou
    même type **connu** et coordonnées identiques. Les coordonnées ne prouvent **jamais** rien entre
    types différents ni entre types inconnus — un contenant géocodé reçoit le point de son chef-lieu.
  - `choisir_survivant` — richesse d'abord, rétroliens ensuite, identifiant en dernier recours (règle
    **totale**, donc reproductible). La fusion Gramps unionne les listes mais conserve les **champs
    simples** du survivant : garder une coquille vide effacerait définitivement code et coordonnées.
  - `etager_lieux` — groupement par égalité de nom normalisé, une relation d'équivalence : les groupes
    sont complets dès la lecture et fusionner deux lieux n'en renomme aucun autre. **Aucune boucle de
    convergence n'est donc nécessaire**, contrairement aux personnes. Une fusion automatique ne
    détruit jamais d'information — dès que le lieu absorbé porte un attribut simple que le survivant
    n'a pas, ou une **valeur concurrente**, la paire part en relecture humaine. Le veto se propage à
    toute la grappe, mais **épargne les paires prouvées par un code identique** : sur les grappes à
    deux entités, 92 % des paires qu'il dégradait étaient prouvées canoniquement.
- `PlaceFacts` et les champs `verdict` / `perte_evitee` de `PlaceMergeProposition` (`models/domain.py`).
  `PlaceFacts` porte l'**identifiant du contenant** et non un booléen : deux communes homonymes
  rattachées à des contenants différents sont des entités distinctes, et ne fusionnent pas.
- `PropositionAudit` gagne `date_iso` et `lieu_nom` — la donnée machine à côté de la phrase française,
  pour qu'une commande d'application n'ait jamais à re-parser de la prose.

---

## [0.23.1] - 2026-07-21

> Entrée **reconstituée a posteriori** (2026-07-22) depuis l'historique `v0.23.0..v0.23.1` :
> cette version avait été taguée sans passer par le journal.

### Fixed

- `GrampsCreateEventTool` — le rattachement ne captait que `httpx.HTTPStatusError`. Une **coupure
  réseau** (`RequestError`) survenant entre le POST réussi de l'événement et son rattachement
  échappait donc à la garde, remontait en exception avalée par `@api_tool`, et **perdait le handle
  de l'orphelin** — le défaut même que la 0.23.0 venait de corriger, par l'autre porte.
  `httpx.HTTPError`, base commune, couvre les statuts **et** le réseau. Relevé en revue CodeRabbit.
- Couverture ajoutée pour l'échec du POST lui-même (`success=False`) sur les deux outils de création,
  plus un test d'échec réseau au rattachement.

---

## [0.23.0] - 2026-07-21

> Entrée **reconstituée a posteriori** (2026-07-22) depuis l'historique `v0.22.0..v0.23.0` :
> cette version avait été taguée sans passer par le journal.

### Added

- **Deux outils d'écriture pour l'import de relevés**, dans `gramps/write_tools.py` :
  - `GrampsCreatePersonTool` — crée une personne **nue** : nom principal et genre, rien d'autre.
    Ni événement, ni filiation — ce sont des écritures séparées et explicites. La casse du nom
    reste à la charge de l'appelant, comme partout dans la couche d'écriture.
  - `GrampsCreateEventTool` — crée un événement (type, date, lieu, citation) et le rattache à une
    personne en **append-only** sur `event_ref_list`. `birth_ref_index` / `death_ref_index` ne sont
    posés **que s'ils étaient absents** : un pointeur vital existant n'est jamais écrasé. Un handle
    synthétique `DRYRUN:` n'entre jamais dans un objet réellement écrit.

### Fixed

- `GrampsCreateEventTool` — **l'orphelin est désormais signalé**. Le rattachement est un second
  write non transactionnel : s'il échoue, l'événement **existe déjà**. Laisser `@api_tool` tout
  avaler en une erreur indistincte perdait le handle et faisait passer une création réussie pour
  un refus. L'outil rend donc un **succès qualifié** — `attached: False` plus le handle de
  l'orphelin, seule prise pour le retrouver.

### Changed

- CI : actions GitHub portées sur Node 24, fin des avertissements Node 20.

---

## [0.22.0] - 2026-07-21

### Added

- **Fusion des doublons de personnes** — la détection passe du simple encadré de rapport à un
  pipeline en trois étages (`auto` / `arbitrage` / `rejet`). Toute l'analyse est **pure**,
  testée hors ligne ; l'orchestration réseau vit dans `genecrew`.
  - `analysis/phonetics.py` — clé phonétique française, **pour le rappel uniquement, jamais une
    preuve**. Elle rapproche les graphies (`Jacquet`/`Jaquet`, `Lelièvre`/`Le Lievre`) tout en
    **séparant** `Jacquet`/`Jacquier` et `Pagan`/`Pagani` — les deux plus grosses familles de
    l'arbre, qui sont des lignées distinctes (`marie pagan` ≈ `marie pagani` à 0,957 en
    similarité lexicale : la ressemblance de nom ne peut donc jamais prouver l'identité).
  - `analysis/duplicates.py` — **blocking multi-clés** : cinq clés (nom exact, phonétique+initiale,
    patronyme+année ±2, famille conjugale, famille parentale). Les deux clés familiales rattrapent
    les personnes **sans date de naissance**, que R10 ignorait totalement. Garde `MAX_BLOC` contre
    l'explosion quadratique (`Pagan` seul, 151 personnes, produirait 11 325 paires).
  - `analysis/duplicates.py` — **étagement** : `auto` sur preuve **structurelle** (date de naissance
    exacte identique + mêmes parents ; ou date exacte identique seule ; ou conjoint + enfant commun),
    `arbitrage` sur preuve partielle, `rejet` sur ressemblance de nom seule. `date_complete` n'accepte
    que le modificateur **exact** : `avant`/`après`/`environ`/intervalle/span bornent une date sans la
    fixer et tombent en arbitrage. Corpus de pièges couvrant frères homonymes, jumeaux, père/fils,
    Pagan/Pagani, concordance sur l'année seule.
  - `analysis/merge_plan.py` — grappes **union-find** (A≈B et B≈C forment une seule grappe à un seul
    survivant : fusionner par paires laisserait un `merge` partir sur un handle supprimé), choix
    déterministe du **phoenix** (complétude, puis citations, puis `gramps_id`), et **patch de genre**.
  - `GrampsMergePeopleTool` — l'appel de fusion réel (`POST /people/{phoenix}/merge/{titanic}` ;
    le phoenix survit, le titanic est supprimé). **Câblé à aucun agent** du crew — la fusion n'est
    invoquée que par l'orchestration déterministe côté `genecrew`.

### Notes

- `Person.merge()` de Gramps n'unit **pas** le genre : celui du phoenix écrase celui du titanic sans
  trace. Le patch de genre calculé par `merge_plan` doit être appliqué **avant** la fusion — d'où le
  seul champ scalaire patché, borné à `Literal[0, 1] | None` (un genre inconnu ne se patche pas).

## [0.21.1] - 2026-07-20

### Fixed

- **Aucune piste sans concordance.** `pistes_wikidata` émettait une `Piste` pour *chaque*
  résultat de recherche, alors que `mwapi/EntitySearch` est une recherche **floue** sur le
  nom : on publiait la sortie brute d'un moteur de recherche comme des « pistes ». Mesuré
  sur 40 personnes d'un arbre réel : 13 des 21 pistes émises (62 %) ne portaient **aucun**
  facteur de concordance. Une ligne sans concordance ne produit désormais plus rien — une
  divergence seule ne suffit pas non plus. `pistes_dhs` en hérite sans modification, car il
  saute déjà les lignes dont `pistes_wikidata` ne tire rien. Wikidata passe de 21 à 8 pistes
  sur cet échantillon, le DHS de 2 à 1.
- **Patronyme vide.** Dans `pistes_wikidata`, `mots(person.surname) <= mots_label` était
  *vacuement vrai* quand le patronyme est vide : un prénom commun suffisait alors à décrocher
  le facteur « nom » sans aucune preuve de patronyme. La garde existait déjà mot pour mot dans
  le module frère `gallica.py` ; les deux sont désormais alignés.

---

## [0.21.0] - 2026-07-20

### Added

- **Paquet `tools/genealogy/pistes/`** : une fonction pure par source d'archives, qui
  traduit un résultat d'API en objet `Piste` — aucun appel réseau, la collecte reste dans
  les outils appelants. Quatre modules :
  - `matchid.py` — déménagé depuis l'application `genecrew`, sans changement de
    comportement.
  - `wikidata.py` — dérive une `Piste` d'un résultat SPARQL Wikidata.
  - `dhs.py` — projection de Wikidata via la propriété `P902` (identifiant Dictionnaire
    Historique de la Suisse), dérivée ligne par ligne (pas par position).
  - `gallica.py` — livré, pur et testé, mais **volontairement non exposé** par `genecrew` :
    mesuré contre l'API réelle, le SRU de Gallica rend des notices de *collection*, pas
    d'article — une piste dirait seulement « ce nom est quelque part dans ce volume de
    500 pages ». L'API adéquate (`services/ContentSearch`, qui rend des passages avec
    numéro de page) impose une conception à deux étapes et fera l'objet d'un sous-projet.
- `EventFact` porte désormais `place` et `place_name`, peuplés depuis le `profile` de
  l'API Gramps sans requête supplémentaire.

---

## [0.20.0] - 2026-07-20

### Changed

- **`Piste.force` est désormais dérivé, pas saisi** (`models/domain.py`) — durcissement suite
  à revue finale de trois défauts liés :
  - `force` n'est plus un paramètre du constructeur : c'est un `@computed_field` pydantic v2,
    calculé depuis `concordances`/`divergences` à chaque accès et sérialisé normalement dans
    `model_dump()`/`model_dump_json()`. Un appel legacy qui passerait encore `force=...` voit
    le kwarg ignoré silencieusement (`extra="ignore"`, comportement par défaut de pydantic) —
    la valeur calculée l'emporte toujours. **Rupture de signature** (d'où le mineur, pas le
    correctif) : tout appelant construisant `Piste(..., force="forte")` doit retirer cet
    argument.
  - La règle de calcul (déplacée depuis le paquet applicatif `genecrew`, qui ne peut
    structurellement pas être une dépendance de cette bibliothèque) vit maintenant à côté du
    modèle : forte = au moins deux facteurs concordants **distincts** et aucune divergence.
    Toute future source de *cette* bibliothèque (Gallica, Wikidata, …) peut désormais
    l'invoquer sans détour par l'application appelante.
  - `concordances` prend un vocabulaire fermé (`FacteurConcordance`, `Literal["nom",
    "prénom", "date complète", "lieu", "unité militaire", "profession"]`) au lieu de `str`
    libre. Une source qui voudrait faire valoir « né en 1888 » est refusée par pydantic avant
    même d'atteindre la règle — l'année seule n'est jamais discriminante (trop d'homonymes
    partagent une naissance la même année) et n'a délibérément pas sa place dans ce
    vocabulaire : elle qualifie une date, elle n'en constitue pas une.
  - La règle déduplique désormais `concordances` avant de compter les facteurs : mesuré,
    `["nom", "nom"]` valait `"forte"` (deux entrées, un seul facteur réel) ; c'est maintenant
    `"faible"`.
  - Toujours catégoriel, délibérément : pas de score, pas de pondération, pas de seuil
    configurable — un score peut valoir 1.0 en masquant une ambiguïté, constaté sur ce projet.

---

## [0.19.3] - 2026-07-20

### Added

- **`Piste`** (`models/domain.py`) : le modèle des pistes de recherche (Phase 4).
  Une piste n'est jamais un fait — aucune citation n'est créée à ce stade. Porte
  l'identité de la source (ark, id MatchID, Q-item) ou, à défaut, une clé dérivée
  marquée comme telle ; `url` reste `None` plutôt que d'être fabriquée. `force`
  est un `Literal["forte", "faible"]`, calculé et non saisi.

---

## [0.19.2] - 2026-07-20

### Fixed

- **Bug critique** dans le résolveur des ex-communes françaises (`geo/france_ex_communes.py`) :
  `wdt:P576` (date de dissolution) rend toujours un `xsd:dateTime` complet, quelle que soit la
  précision réelle de la déclaration Wikidata — une dissolution saisie en précision ANNÉE
  ressortait "1972-01-01T00:00:00Z" comme si c'était une date exacte, sans que la garde
  d'unicité d'entité (qui vérifie le *successeur*, pas la *précision*) ne s'en aperçoive.
  `rows[0]` pouvait alors choisir arbitrairement la ligne en précision année, fabriquant une
  borne de rattachement inventée — mesuré en direct sur Huppain (INSEE `14340`) : une date
  `1972-01-02` fabriquée de toutes pièces, alors qu'aucune date fiable n'aurait dû être posée.
  Une fausse date de fusion route silencieusement des actes vers la mauvaise branche de la
  hiérarchie — pire qu'une date absente.
  - La requête SPARQL passe désormais par le nœud de déclaration (`p:P576/psv:P576`) pour lire
    `wikibase:timePrecision` en même temps que la valeur, au lieu du raccourci `wdt:P576`.
  - `wikidata_ex_commune` n'accepte plus qu'une dissolution en précision JOUR (`prec=11`) ;
    toute autre précision, ou précision absente, dégrade vers une chaîne non datée.
  - Plusieurs déclarations `P576` *distinctes* en précision jour (dates contradictoires)
    restent une ambiguïté — pas de choix arbitraire, pas de datation. Plusieurs lignes portant
    la *même* valeur en précision jour restent du fan-out SPARQL bénin (déjà géré par la garde
    d'unicité d'entité) et ne bloquent pas la datation.

## [0.19.1] - 2026-07-20

### Fixed

- `ruff check src tests` is clean (was 19 errors, long-standing). Removed 4 genuinely unused imports in tests, dropped a dead unpacking in `config/cache.py` (`val` was bound and never read), split a semicolon statement, and declared `__all__` in `core/__init__.py` so the `api_tool` re-export is explicit rather than an apparently-unused import.

### Changed

- Added a `[tool.ruff.lint.per-file-ignores]` section — the repo had no ruff config at all. `models/__init__.py` and `models/reports/__init__.py` are pure re-export aggregators, so `F403` is suppressed there with a comment explaining why: enumerating the 51 re-exported names by hand would risk silently dropping one from the public surface. Verified unchanged at 51 names.

---

## [0.19.0] - 2026-07-20

### Added

- **Résolveur des ex-communes françaises** (`geo/france_ex_communes.py`) : les communes
  fusionnées (loi Marcellin) sont absentes de `geo.api.gouv.fr/communes`, ce qui faisait
  échouer `resolve_fr` et basculer sur Nominatim — lequel trouve le point mais perd toute
  la hiérarchie. Le nouveau résolveur interroge `/communes_associees_deleguees` pour le
  rattachement et le code INSEE propre, puis Wikidata (SPARQL par `P374`) pour la date de
  dissolution, le successeur et les coordonnées.
- Le lieu obtient **deux rattachements datés** : sous son département avant la fusion, sous
  la commune absorbante après. La borne est `merged_on` = dissolution + 1 jour — poser la
  date de dissolution ferait démarrer le rattachement moderne un jour où la commune existait
  encore.
- `sparql_rows()` dans `tools/web/wikidata.py` : transport SPARQL libre, utilisable hors
  d'un `BaseTool` CrewAI.
- `pick_exact_by_name()` dans `geo/france.py`, extrait de `_resolve_fr_by_name` sans
  changement de comportement et partagé par les deux résolveurs français.

### Notes

- **Garde de recoupement** : les chaînes ne sont datées que si le successeur donné par
  Wikidata concorde avec le `chefLieu` de `geo.api.gouv.fr`. Sinon, ou si la date est
  incalculable, une seule chaîne non datée — jamais de date inventée, une fausse date de
  fusion routant silencieusement des actes vers la mauvaise branche.
- **GPS** : les coordonnées Wikidata (centre du bourg) priment sur le `centre` de l'API
  (centroïde du territoire), ~700 m d'écart mesuré. Exception assumée à `map_commune`.
- Couverture mesurée sur 12 ex-communes de la Meuse : Wikidata `P576` 12/12 en précision
  jour, avec des dates variées (1972-06-30, 1973-02-28) que l'année seule de Wikipédia
  aurait perdues.

---

## [0.18.0] - 2026-07-20

### Fixed

- **15 `BaseTool` subclasses were on neither the library nor the MCP surface.** `mcp_server.register_all` iterates `__all__`, so a tool missing from it is invisible on both surfaces; these had accumulated since 0.13.0 and were reachable only by full module path. Now exported: `GallicaSearchTool`, `WikidataSparqlTool`, `InseeDecesSearchTool`, `GenealogyCheckPersonTool`, `GenealogyFindDuplicatesTool`, `GenealogyResolvePlaceTool`, `GrampsCreateNoteTool`, `GrampsEnsureTagTool`, `GrampsAttachTool`, `GrampsEnsureSourceTool`, `GrampsCreateCitationTool`, `GrampsAttachCitationTool`, `GrampsAddUrlTool`, `GrampsAttachMediaTool`, `GrampsUploadMediaTool`. The MCP surface goes from 104 to **119** tools, all registering with zero skips.

### Added

- `tests/test_export_surface.py` — the reason the gap went unnoticed was that nothing checked it. Walks the package, asserts every defined `BaseTool` subclass appears in `__all__`, and asserts `register_all()` skips nothing.
- `tests/test_genealogy_media_tools.py` — coverage for the URL/media writers shipped without tests in 0.17.0, including the guard that a `DRYRUN:` media handle is never written as a real `MediaRef`.

---

## [0.17.0] - 2026-07-20

### Added

- **Military-death gazetteer matching** (`tools/genealogy/militaires.py`) — queries the "Morts pour la France" dataset and scores candidates through a new shared identity module (`analysis/identity.py`), so death matching and military matching now share one scoring contract instead of duplicating heuristics.
- **Place Wikipedia enrichment primitives**: frwiki geosearch (`tools/web/wikipedia.py`) plus Gramps URL/media write tools (`GrampsAddUrlTool`, `GrampsAttachMediaTool`, `GrampsUploadMediaTool` in `gramps/write_tools.py`) — attaches a Wikipedia article and its lead image to a resolved place.

### Fixed

- Militaires query limit raised 50 → 2000: common surnames pushed the correct row off the truncated result page, so the right match was never scored.
- Nominatim requests now send `accept-language=fr`. Toponyms returned in a local script (Cyrillic, Greek, Arabic) scored near zero against the French tree name and silently lost their match.

---

## [0.16.0] - 2026-07-19

### Added

- **source→citation write chain** (`gramps/write_tools.py`): `GrampsEnsureSourceTool` (idempotent source lookup-or-create), `GrampsCreateCitationTool`, `GrampsAttachCitationTool` — lets a run turn a validated external find into a real Gramps citation attached to the object it supports.
- **D-rules** (`analysis/`): pure, deterministic correction detectors that reproduce the LLM crew's finds at zero token cost.

### Fixed

- Death-match scoring strips tree-artifact commas from given names before comparison.
- Year-only birth concordance is capped at 0.5, so a bare year agreement can never cross the match threshold on its own.
- `D-mariage-des-parents` also matches on same-year dates — real trees mix date precisions.

---

## [0.15.0] - 2026-07-19

### Added

- **Deterministic MatchID death scoring** (`tools/genealogy/matchid.py`): `search_deces` plus `score`/`best_deces_match`, replacing LLM judgement with a reproducible scoring function.

### Fixed

- The Wikipedia tool's `action` field is a `Literal` rather than an enum, so the generated schema is inlined instead of emitting a `$ref` that several LLM providers reject.

---

## [0.14.0] - 2026-07-19

### Fixed

- **Provider-portable input schemas** — removed `Optional` unions from the schemas of crew-wired tools. Union types serialize to `anyOf`, which some LLM tool-calling providers refuse, making the affected tools uncallable.

### Changed

- Untracked local artifacts (`.cache`, `.playwright-mcp`, `cassini.html`) swept into the repo by a bulk `git add`.

---

## [0.13.0] - 2026-07-19

### Added

- **On-demand analysis tools**: `GenealogyCheckPersonTool` and `GenealogyFindDuplicatesTool` (`analysis/tools.py`) expose the pure consistency rules to an agent; `GenealogyResolvePlaceTool` (`geo/tools.py`) exposes the geo engine.
- **Free external research APIs**: `WikidataSparqlTool` (`tools/web/wikidata.py`), `GallicaSearchTool` (`tools/web/gallica.py`), `InseeDecesSearchTool` (`tools/genealogy/matchid.py`) — keyless sources for corroborating a fact.
- **Append-only note/tag write tools**: `GrampsCreateNoteTool`, `GrampsEnsureTagTool`, `GrampsAttachTool` — a run records its findings without mutating existing data.
- **US place resolver** via an embedded Census Gazetteer, and an **authoritative Germany resolver** (AGS + name/Land) backed by an embedded BKG VG250 gazetteer of 10 981 communes (`scripts/` build script included). 8-digit AGS codes parse as authoritative German codes while keeping the Land.
- Resolve French places **by name** — a unique hit is authoritative, homonyms become a proposition.
- `FactsFetcher` + facts mappers migrated from genecrew: domain logic belongs in this package, not in the orchestration repo.
- Monotone core-name `best_similarity` in `geo/score.py`; colonial-era country transitions added to `data/transitions.csv`.
- JWT is cached to disk (atomic write, mode 0600, non-dict guard, login retry on 429) so repeated invocations stop re-authenticating and tripping rate limits.

### Fixed

- `GrampsCreatePlaceTool` reads the transaction array returned by the 201 response (live bug — the created handle was never recovered).
- Ambiguity now wins over a score of 1.0; a lone postal code is no longer parsed as an INSEE code.
- A right-truncated flat place name parses as a commune, not a country.
- Swiss and Nominatim resolvers score the core name and pick the argmax; the Swiss resolver restricts to municipalities and adds the canton to the chain (`Suisse > Canton > Commune`); Nominatim drops the importance multiplier.
- US resolver uses the parsed region for the state, with a collision guard.
- Geo resolvers are throttled, transitions are cached, and the place tools are exported.

---

## [0.12.0] - 2026-07-19

### Added

- **Place-standardization domain** (`tools/genealogy/geo/` + `standardize/places.py` + place models). Parses flat GEDCOM-imported place strings and resolves them to a canonical modern name, a typed parent hierarchy, and WGS84 coordinates, via a **country-routed resolver chain**:
  - Pure `standardize/places.py` — `parse_pname` (positional parser with shift detection, index-based segment handling) and `normalize_country`; dataset-agnostic, offline.
  - `geo/registry.py` routes a `ParsedPlace` to a country resolver, falling back to a worldwide geocoder; `decide_action` maps the resolution score to `ecrire` / `proposition` / `indecidable`. Adding a country = one registry entry.
  - Resolvers (each a thin monkeypatchable httpx wrapper + a pure mapper returning the `ResolvedPlace` contract): `france.py` (authoritative INSEE code → `geo.api.gouv.fr`, score 1.0), `suisse.py` (swisstopo GeoAdmin — reads WGS84 `lat`/`lon`, never the LV95 `x`/`y` grid), `nominatim.py` (worldwide OSM fallback, selects the best fuzzy-score candidate). `geo/score.py` provides `similarity`/`fuzzy_score` + an ambiguity guard.
  - **Data-driven temporal transitions** (`geo/transitions.py` + `data/transitions.csv`): emits two dated parent chains (before/after a sovereignty change) + a dated alt name when a dataset row matches — the code contains no country-specific logic (empty dataset → single undated chain).
  - Place domain models: `ParsedPlace`, `PlaceLevel`, `DatedChain`, `DatedName`, `ResolvedPlace` (the resolver contract), `PlaceProposition`, `PlaceMergeProposition`.
- **Place write tools** (`gramps/write_tools.py`): `GrampsCreatePlaceTool` (creates a parent/leaf place; synthetic `DRYRUN:<name>` handle in dry-run), `GrampsUpdatePlaceTool` (enriches a leaf in place — name/type/WGS84 lat-long/code/placerefs/alt-names — no-op when already conforming), `GrampsMergePlacesTool` (human-triggered leaf merge via the native `/merge/` endpoint). `date_qualifier_to_gramps_date` converts `"avant/après YYYY-MM-DD"` placeref qualifiers into real Gramps `Date` objects. All gated by `effective_dry_run`.

---

## [0.11.1] - 2026-07-19

### Fixed

- Dry-run gating is now **safe by default**. The genealogy write tools share a new `effective_dry_run(dry_run)` helper: when `GENECREW_DRY_RUN` is **absent**, the default is now to **simulate** (never silently write — previously an absent variable meant *write*). The env switch still only ever *forces* simulation, and an explicit `dry_run=True` always wins; set `GENECREW_DRY_RUN=false` to write for real. The genecrew orchestration passes this effective value into its reports, so a run can no longer print `écritures appliquées` while writing nothing.

---

## [0.11.0] - 2026-07-18

### Added

- `GrampsUpdateGenderTool` — the genealogy domain's first write of a *fact* (a person's `gender`, int `0=F/1=M/2=U`) to Gramps Web. Bounded, high-confidence use only (consumed by genecrew's `gender-apply` above a confidence threshold). Gated by the double dry-run switch (the `dry_run` param OR the global `GENECREW_DRY_RUN` env — the env can only force simulation, never force a write), no-ops when the requested gender already equals the current one, and returns the `ok()` envelope with `{old, new, dry_run, noop}`. Exported in `__all__` (reusable by a future writer agent). See ADR 0009 in the genecrew repo.

---

## [0.10.0] - 2026-07-18

### Added

- Gender-inference domain: the `Proposition` Pydantic model (the project's first proposition emitter — a proposal for human review of a *fact*, reused by future chantiers) and `analysis/gender.py` (`normkey`, `infer_sex`, `load_prenoms_table`, `GenderInference`). Conservative policy: infer a sex only when the dominant sex is ≥ 95 % over ≥ 50 births. `normkey` canonicalizes to uppercase, strips accents, and folds apostrophe/hyphen Unicode variants (incl. U+2019).
- Sovereign, offline **prénom→sexe reference table** embedded in the wheel (`tools/genealogy/data/prenoms_sexe.csv`, ~85 500 names) plus `scripts/build_prenoms_sexe.py`, which provisions the table by **auto-downloading** its sources — INSEE (Fichier des prénoms, Licence Ouverte) + OFS/BFS (Swiss population first names by year of birth). The Swiss source fixes franco-Swiss false positives at the data level (e.g. "Ami", "Marie-Joseph" → abstention) and adds Swiss-German names (Beat/Ueli/Reto). `--no-ofs` builds from INSEE only.

---

## [0.9.0] - 2026-07-18

### Added

- Name-casing standardizer, the genealogy domain's **first writer** to Gramps: `GrampsUpdateNameTool` (`gramps/write_tools.py`) re-capitalizes a person's primary name (given + surnames, treated as separate fields) backed by `standardize/names.py` (French-aware pure helpers: particles, `de`/`d'`, hyphenated compounds, apostrophe/hyphen Unicode). Casing = *form*, so it writes directly — but is guarded by a **case-only invariant** (`is_case_only_change`) that refuses any change altering the letters (it can re-capitalize, never re-spell) and skips incomplete names (`?`/digits). Gated by the `dry_run` param and the global `GENECREW_DRY_RUN` env switch.

### Fixed

- Dropped a Mc/Mac capitalization heuristic that corrupted French names (`MACRON` → `MacRon`).

---

## [0.8.1] - 2026-07-17

### Added

- Completeness rules D1 (person with no date at all), D2 (free-text / unsortable date), D3 (unknown gender) in `analysis/rules.py`.

---

## [0.8.0] - 2026-07-17

### Added

- Deterministic genealogy audit (no LLM): hand-written domain models (`models/domain.py` — `PersonFacts`/`FamilyFacts`/`Anomaly`/`DuplicateCandidate`) and pure consistency rules in `analysis/`: person rules R1, R2, R6–R9 and family rules R3, R4, R5 (`rules.py`), plus the duplicate finder R10 (`duplicates.py`, difflib + birth-year window). Date comparisons use the Gramps Julian-day `sortval`, so unknown dates never produce a false positive.

---

## [0.7.0] - 2026-07-17

### Added

- Genealogy domain (Phase 0), consumed by the sibling `genecrew` project: `gramps/client.py` (pure httpx + JWT Gramps Web client with read helpers), `models/gramps_generated.py` (Pydantic models generated from the Gramps Web OpenAPI 3.17.0 spec), and 5 read-only Gramps `BaseTool`s (`gramps/read_tools.py`: search, get-object, list-people, tree-stats, timeline).

---

## [0.6.2] - 2026-07-16

### Security

- Pinned `json-repair` to `>=0.60.1` via `[tool.uv] override-dependencies`, fixing [GHSA-xf7x-x43h-rpqh](https://github.com/advisories/GHSA-xf7x-x43h-rpqh) (CVSS 7.5, high) — an unbounded-loop CPU DoS in `SchemaRepairer.resolve_schema()` triggered by a circular JSON Schema `$ref`. `json-repair` is a transitive dependency pulled in by `crewai` (`crewai~=1.15.2` pins `json-repair~=0.25.2`, itself vulnerable); `crewai` only calls the plain `repair_json(text)` form and never passes the `schema=` kwarg that reaches the vulnerable code path, so the override is a safe, non-breaking upgrade (0.25.3 → 0.61.2 in `uv.lock`).

---

## [0.6.1] - 2026-07-16

### Fixed

- `mkdocs.yml` nav referenced two spec/plan files with a filename typo (`crewai-custom-tools-universal-monolith*` instead of the actual `crew-custom-tools-universal-monolith*`), which aborted `mkdocs build --strict`. Also added 3 previously-orphaned docs pages (OSINTFR plan/spec, the 2026-07-08 centralization plan) to the nav.
- Refreshed stale counts/links left over from the wave3-analytics merge: tool count (87→93, plus the new Files category) and test count (224→423) in `README.md` and `CLAUDE.md`; release version references (v0.1.1→v0.6.0) in `README.md` and `docs/USER_GUIDE.md`.

### Changed

- Refreshed `uv.lock` transitive dependency versions (e.g. `anyio` 4.14.1→4.14.2, `cffi` 2.0.0→2.1.0); `pyproject.toml` unchanged.

---

## [0.6.0] - 2026-07-15

### Added

- New `tools/files/` surface: `FileReadTool` / `DirectoryReadTool`, ported from finwiz. Deliberate exception to the package-wide `ok()`/`err()` JSON envelope — both return **plain strings** (the file/listing content an agent reads), not the standard envelope.
- New `tools/analytics/` surface: `ValuationTool`, `ETFAnalysisTool`, `RegulatoryComplianceTool`, `PositionSizingTool`, `PriceTargetCalculator`, `APlusScoringTool`, `APlusScreeningTool`. All are pure computation over caller-supplied or static-lookup-table data — none call yfinance or any other network API, so none carry the `@api_tool` rate-limit decorator used by network-backed tools elsewhere in this package.
  - `PositionSizingTool` and `PriceTargetCalculator` are **plain classes**, not `BaseTool` subclasses — they're programmatic APIs for callers like finwiz's rebalancing crew (returning typed pydantic models directly) and are therefore exported but do **not** register on the MCP tool surface. `ValuationTool`, `ETFAnalysisTool`, `RegulatoryComplianceTool`, `APlusScoringTool`, and `APlusScreeningTool` are `BaseTool`s and register automatically.
  - `APlusScreeningTool` is finwiz's `MarketScreeningTool` **renamed** (MCP/tool name `"aplus_screening"`) to avoid colliding with this package's pre-existing, simpler `tools/finance/screening.py::MarketScreeningTool` (tool name `"market_screening"`).

### Fixed

- `composite_score` fallback bug: finwiz's raw score dict put the composite score only under `analysis_summary.composite_score`, but downstream consumers (e.g. `ScreeningRanking`) read `score_result.get("composite_score", 0.5)` at the top level — silently defaulting every candidate to 0.5. `APlusScoringTool` now also emits `composite_score` at the top level of its result, alongside the existing nested copy.

---

## [0.5.1] - 2026-07-15

### Added

- `AlphaVantageOverviewTool` payload gains `sector`/`industry`/`market_cap`/`eps`/`revenue_ttm`/`description`; `EnhancedCryptoAnalysisTool` payload gains `volume_24h` (`current_price_usd`/`market_cap_usd`/`circulating_supply`/`total_supply`/`max_supply` were already present and are unchanged). Additive; no signatures changed.

---

## [0.5.0] - 2026-07-15

### Added

- Rate limiter: bounded waits (`CREWAI_TOOLS_RATE_LIMIT_MAX_WAIT`, default 120s) surfacing as `err()` envelopes via `RateLimitExceeded`; WARNING log for waits >5s; new provider limits for `TickerValidation`, `CoinGecko`, `DeFiLlama`.
- `crewai_custom_tools.tools.finance` subpackage now re-exports the full finance tool set (previously top-level only).

### Fixed

- SEC tool's rate-limit provider key (`SEC-EDGAR` → `SECEdgar`) — SEC calls were unthrottled.
- `YahooFinanceCompanyInfoTool` falls back to `info["revenueGrowth"]` on ANY financials-fetch failure (network errors previously errored the whole call).

---

## [0.4.0] - 2026-07-14

### Breaking

- `PerplexitySearchTool`: `focus`/`recency` params replaced by `model`/`top_k`/`search_recency`/`search_domain_filter`; construction now raises `ValueError` without `PERPLEXITY_API_KEY` (or legacy `PPLX_API_KEY`). The recency filter is now actually sent (`search_recency_filter`).
- `crewai` floor raised to `>=1.15.1`.
- MCP server: without a Perplexity key, `perplexity_search` is no longer listed by the MCP server (previously listed and errored per-call); the server itself still starts and serves all other tools.

### Added

- `parse_tool_result()` / `ToolResultError`: canonical envelope parsing for programmatic consumers.
- `require_api_key()`: fail-fast key validation with multi-var fallback.
- Provider-keyed synchronous rate limiter, enforced by `@api_tool` (disable with `CREWAI_TOOLS_RATE_LIMIT_DISABLED=1`).
- `perplexity_structured()` async function (JSON-schema structured research, ported from finwiz).
- `prefetched_data` batch mode on `YahooFinanceTickerInfoTool` and `YahooFinanceHistoryTool`.
- Yahoo ticker/history results now carry `timestamp` / `market_time` / `data_time` / `data_source`; ticker info gains finwiz's extended fundamental fields.
- `YahooFinanceCompanyInfoTool`: revenue growth calculated from actual financials; `debt_to_equity` converted to a ratio.

---

## [0.3.1] - 2026-07-09

### Fixed

- **`UnifiedRssTool` timezone-consistent date filtering** (#3): the day-granular cutoff was
  built from `datetime.now()` (naive local time) but compared against feed entry dates that
  feedparser normalises to UTC, skewing the boundary by the host's UTC offset on non-UTC
  servers. The cutoff is now naive-UTC, and `_entry_pub_date` converts tz-aware string dates
  to UTC before dropping tzinfo, so every date is directly comparable.
- **`UnifiedRssTool` bounded feed fetch** (#4): `feedparser.parse` had no network timeout, so
  a slow or hanging feed could stall the whole aggregation run. Each fetch now runs under a
  default socket timeout (`FEED_FETCH_TIMEOUT_S`, 20s), restored afterwards; a timing-out feed
  is caught and recorded as an invalid source instead of blocking.

---

## [0.3.0] - 2026-07-08

### Fixed

- **`SaveToRagTool` collection injection**: the tool now accepts an optional pre-configured
  `rag_tool` via its constructor (`SaveToRagTool(rag_tool=...)`) and stores into it, instead of
  always instantiating a bare default `RagTool()` — which wrote to the wrong chromadb
  collection/embeddings and silently broke save->retrieve. Falls back to a default `RagTool()`
  only when none is injected. Keeps the `save_to_rag` name, args schema, and
  `{success,data,error}` envelope.
- **`UnifiedRssTool` full-pipeline restoration**: restored the
  `_run(opml_file_path, days=7, output_file_path=None, invalid_sources_file_path=None)`
  signature, `RssFeeds` JSON **output-file writing**, article **content-scraping** (via the
  in-package resilient `UnifiedScraperTool`, with an optional Newspaper3k fast path), and
  **invalid-source tracking**. This makes the tool a drop-in for programmatic callers that
  invoke `._run(opml, days, output_file_path)` positionally and rely on the written file as the
  output.

### Added

- `tools/web/rss_models.py`: `Article` / `FeedWithArticles` / `RssFeeds` pydantic models
  describing the aggregated RSS JSON output contract.
- Dependency: `python-dateutil` (pure-Python) for RSS entry date fallback parsing.

## [0.2.0] - 2026-07-08

### Added

- **`ToolResult` envelope (`core/results.py`)**: every tool now returns a uniform
  `{"success": bool, "data": <any>|null, "error": <str>|null}` JSON string via the
  `ok()` / `err()` helpers, so callers can always distinguish a genuine failure from an
  empty-but-successful result.
- **47 newly centralized / rebuilt tools** (library now exports 87 tool classes). New
  capabilities: additional search providers (Brave, Tavily, SerpApi, Hybrid) and standalone
  scrapers; CoinMarketCap list/news/historical; enhanced ETF/crypto/DeFi analysis; TwelveData
  indicators; Alpha Vantage news-sentiment; ChartImg; structured Perplexity; INSEE Sirene,
  BODACC, GDELT, Google News RSS, Hunter finder/verifier; CLI-backed recon (sherlock,
  maigret, theHarvester, net_recon) with graceful gating; data-centric + report-writer
  tools; Geoapify, TechStack, Wikipedia processing, RSS aggregators, delegating email; and
  6 clean-rebuilt analytics tools (market screener, standardized risk scoring, SEC EDGAR
  analysis, VADER sentiment + cross-asset comparator, template-free HTML generator).
- **`core/cli_runner.py`**: hardened no-shell subprocess runner (target validation,
  PATH resolution, mandatory timeout, stdout cap) backing the CLI-based OSINT tools.
- **Full MCP parity**: `mcp_server.py` auto-registers every exported tool (81) instead of
  a hand-written subset.

### Fixed

- **~50 correctness/security findings** across the ported tools, including: Yahoo ETF
  holdings (called non-existent yfinance methods → always empty; now `get_funds_data()`),
  Yahoo news deprecated keys, history %-change divide-by-zero, Perplexity dead `focus`
  param + unguarded parse, username detection (HTTP-200-only → found/unknown/absent
  heuristic), RDAP `.co.uk` handling, both report renderers (one errored, one blanked),
  RAG false-success, AccuWeather cleartext key, Airtable URL encoding, and many non-JSON
  returns. Reporting **templates are now packaged** so they work on a `pip install`.

### Security

- Stored-XSS in HTML report rendering closed (escape untrusted section content).
- XXE hardening for OPML parsing via `defusedxml`.
- AccuWeather calls moved to HTTPS.

### Changed

- `@api_tool` returns a JSON error envelope on failure (was empty `{}`/`[]`).
- Added dependencies: `defusedxml`, `tldextract` (both pure-Python).

## [0.1.0] - 2026-07-05

### Added

- **Unified Caching Layer (`config/cache.py`)**:
  - Structured, thread-safe, self-healing file and memory cache using `.crewai_cache/`.
  - Added `@cache_api_call` decorator to easily apply caching to core sync functions.
  - Implemented SHA-256 and MD5 cryptographic hashing to ensure completely deterministic key generation across restarts (avoiding built-in randomized `hash()`).
  - Added dynamic class instance `self` inspection to strip memory addresses (like `0x...`), preventing cache misses when instance methods are decorated.
  - Robust `FileNotFoundError` and `JSONDecodeError` safety to handle concurrent race conditions.
- **Unified Tool Set (`tools/`)**:
  - `PerplexitySearchTool` (in `tools/web/perplexity.py`) featuring standard requests timeouts, dual-return formats (`"json"` or `"markdown"`), and multi-environmental api-key validation.
  - `YahooFinanceNewsTool` (in `tools/finance/yfinance_news.py`) returning structured news data for financial instruments, wrapped with safety borders.
  - `YahooFinanceTickerInfoTool` (in `tools/finance/yfinance_ticker.py`) extracting a standardized, clean metric subset (P/E ratio, Market Cap, Beta) for assets, ETFs, and cryptos.
- **Top-Level Exports**: Exposes `PerplexitySearchTool`, `YahooFinanceTickerInfoTool`, and `YahooFinanceNewsTool` directly from `crewai_custom_tools`.
- **Comprehensive Pytest Suite**: 40 unit and integration tests covering versions, caching layers, filename collision, metadata preservation, wraps decorator, error responses, and mock APIs.

### Changed

- **Modular Packaging**: Renamed library package from `crewai-tools` to `crewai-custom-tools` to prevent PyPI conflicts, updating all workspace files and plan structures.
- **Extracted Optional Extras**: Isolated `yfinance` under `[finance]` extra and `pytest-mock` under `[dev]` extra inside `pyproject.toml` to minimize base deployment size.
- **Standard Logging**: Swapped all custom logger formats (Loguru bracket syntax `{}`) to standard Python `logging` for lightweight compatibility.
- **Failure Non-Caching Policy**: Refactored financial news fetching to ensure exception payloads and rate limits are never cached permanently, allowing immediate recovery on subsequent execution.
