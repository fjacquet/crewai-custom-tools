# Table prénoms → sexe (INSEE + OFS)

`prenoms_sexe.csv` — colonnes `prenom` (clé normalisée : MAJUSCULES, accents
retirés, apostrophes/tirets canoniques), `n_f`, `n_m` (effectifs de naissances).

## Sources (souveraines, hors-ligne une fois téléchargées)

- **INSEE — Fichier des prénoms** (national), CSV `;`, colonnes
  `sexe;preusuel;annais;nombre` (`sexe` 1=M, 2=F ; `preusuel` en capitales sans
  accents ; prénoms rares regroupés sous `_PRENOMS_RARES`, **exclus**).
  Licence Ouverte / Etalab. <https://www.insee.fr/fr/statistiques/8595130>
- **OFS/BFS — Prénoms des nouveau-nés** (Suisse), extraits en deux CSV `;`
  `prenom;nombre` (`ofs_masculin.csv`, `ofs_feminin.csv`).
  <https://www.bfs.admin.ch/bfs/fr/home/statistiques/population/naissances-deces/prenoms-nouveaux-nes.html>

## Régénération

```bash
uv run python scripts/build_prenoms_sexe.py \
  --insee nat.csv --ofs-f ofs_feminin.csv --ofs-m ofs_masculin.csv \
  --out src/crewai_custom_tools/tools/genealogy/data/prenoms_sexe.csv
```

Les fichiers bruts ne sont pas versionnés ; seul `prenoms_sexe.csv` l'est.
