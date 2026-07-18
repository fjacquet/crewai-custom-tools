# Table prénoms → sexe (INSEE + OFS)

`prenoms_sexe.csv` — colonnes `prenom` (clé normalisée : MAJUSCULES, accents
retirés, apostrophes/tirets canoniques via `normkey`), `n_f`, `n_m` (effectifs
agrégés). **Versionné et embarqué** : la fonctionnalité marche prête à l'emploi,
sans téléchargement au runtime. ~85 500 prénoms (France + Suisse).

## Génération / rafraîchissement — une seule commande

Le script **télécharge lui-même** les deux sources et bâtit la table (aucun
fichier à manipuler à la main) :

```bash
uv run python scripts/build_prenoms_sexe.py          # INSEE + OFS
uv run python scripts/build_prenoms_sexe.py --no-ofs  # INSEE seul
```

Il écrit directement `src/crewai_custom_tools/tools/genealogy/data/prenoms_sexe.csv`.

## Sources (souveraines, open data)

- **INSEE — Fichier des prénoms** (fichier national, France 1900→2025),
  Licence Ouverte / Etalab. Zip d'un CSV `;`, colonnes
  `sexe;prenom;periode;valeur;rang` (`sexe` 1=M, 2=F ; `valeur` agrégé par
  prénom×sexe sur toutes les années ; l'ancien en-tête `preusuel;annais;nombre`
  reste toléré). Édition épinglée dans `INSEE_URL`.
  <https://www.insee.fr/fr/statistiques/8595130>
- **OFS/BFS — Prénoms de la population selon l'année de naissance** (Suisse,
  2024). Deux CSV `,` (BOM), colonnes `TIME_PERIOD,firstname,YEAROFBIRTH,VALUE,OBS_STATUS`
  (`VALUE` agrégé par prénom) — un fichier masculin, un féminin. Assets DAM
  épinglés dans `OFS_M_URL`/`OFS_F_URL`. Apporte la couverture suisse (dont
  suisse-allemande : Beat, Ueli, Reto…) et corrige les faux positifs
  franco-suisses (ex. « Ami », masculin romand vu 100 % F par l'INSEE seul).
  Datasets : `mannliche-/weibliche-vornamen-der-bevolkerung-nach-jahrgang-schweiz-2024`
  sur opendata.swiss.

Les fichiers bruts ne sont pas versionnés ; seul `prenoms_sexe.csv` l'est. Les
éditions sont épinglées (à bumper au fil des rééditions).
