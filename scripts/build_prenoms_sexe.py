"""Build the bundled prenoms_sexe.csv — the tool provisions its own data.

By default this DOWNLOADS the official sovereign open-data sources and builds the
prénom→sexe table in one command, with no manual file handling:

    uv run python scripts/build_prenoms_sexe.py

Sources (auto-téléchargées) :
- INSEE « Fichier des prénoms » (naissances France 1900→) — Licence Ouverte.
- OFS/BFS « Prénoms de la population selon l'année de naissance » (Suisse) —
  couvre la branche suisse (dont suisse-allemande) et corrige les faux positifs
  franco-suisses (ex. « Ami », masculin romand).

Offline / test : passer des chemins locaux (--insee / --ofs-f / --ofs-m). Voir
src/crewai_custom_tools/tools/genealogy/data/README.md pour la provenance.
"""

from __future__ import annotations

import argparse
import csv
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from crewai_custom_tools.tools.genealogy.analysis.gender import normkey

# INSEE — fichier national (France, 1900→2025), zip d'un CSV ';',
# colonnes sexe;prenom;periode;valeur;rang (sexe 1=M, 2=F). Licence Ouverte.
INSEE_URL = "https://www.insee.fr/fr/statistiques/fichier/8595130/prenoms-2025-nat_csv.zip"
# OFS/BFS — prénoms de la population selon l'année de naissance (Suisse, 2024),
# CSV ',' (BOM), colonnes TIME_PERIOD,firstname,YEAROFBIRTH,VALUE,OBS_STATUS.
# Assets DAM (opendata.swiss : *-vornamen-der-bevolkerung-nach-jahrgang-schweiz-2024).
OFS_M_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36062345/master"
OFS_F_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36062347/master"
_UA = "genecrew-build/1.0 (open data)"

DEFAULT_OUT = (Path(__file__).resolve().parents[1]
               / "src/crewai_custom_tools/tools/genealogy/data/prenoms_sexe.csv")


def _add(table: dict[str, tuple[int, int]], key: str, n_f: int = 0, n_m: int = 0) -> None:
    f, m = table.get(key, (0, 0))
    table[key] = (f + n_f, m + n_m)


def _fetch(url: str, dest: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())
    return dest


def download_insee(dest_dir: Path) -> Path:
    """Download the INSEE national zip and extract its CSV into dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = _fetch(INSEE_URL, dest_dir / "insee_nat.zip")
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        zf.extract(csv_name, dest_dir)
    return dest_dir / csv_name


def download_ofs(dest_dir: Path) -> tuple[Path, Path]:
    """Download the OFS masculine + feminine population first-name CSVs."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    return (_fetch(OFS_M_URL, dest_dir / "ofs_m.csv"),
            _fetch(OFS_F_URL, dest_dir / "ofs_f.csv"))


def _read_insee(path: str, table: dict[str, tuple[int, int]]) -> None:
    """Aggregate INSEE births by normalized first name × sex, across all years.

    Tolerant to the 2025 header (prenom/valeur) and the older one
    (preusuel/nombre). sexe 1 = masculin → n_m, 2 = féminin → n_f.
    """
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            name = row.get("prenom") or row.get("preusuel") or ""
            key = normkey(name)
            if not key:
                continue
            count = int(row.get("valeur") or row.get("nombre") or 0)
            if row["sexe"] == "1":
                _add(table, key, n_m=count)
            elif row["sexe"] == "2":
                _add(table, key, n_f=count)


def _read_ofs(path: str, table: dict[str, tuple[int, int]], *, female: bool) -> None:
    """Aggregate OFS population counts by first name (VALUE summed over years).

    CSV ',' with a BOM; columns firstname, VALUE (one file per sex).
    """
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = normkey(row.get("firstname", ""))
            if not key:
                continue
            count = int(row.get("VALUE") or 0)
            if female:
                _add(table, key, n_f=count)
            else:
                _add(table, key, n_m=count)


def build(insee: str | None = None, ofs_f: str | None = None,
          ofs_m: str | None = None, out: str | Path = DEFAULT_OUT,
          *, with_ofs: bool = True) -> Path:
    """Build the table. Downloads INSEE (and OFS unless --no-ofs) when paths are None."""
    table: dict[str, tuple[int, int]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _read_insee(insee or str(download_insee(tmp_dir)), table)
        if insee is None and with_ofs and ofs_f is None and ofs_m is None:
            ofs_m, ofs_f = (str(p) for p in download_ofs(tmp_dir))
        if ofs_f:
            _read_ofs(ofs_f, table, female=True)
        if ofs_m:
            _read_ofs(ofs_m, table, female=False)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["prenom", "n_f", "n_m"])
        for key in sorted(table):
            n_f, n_m = table[key]
            writer.writerow([key, n_f, n_m])
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build prenoms_sexe.csv (télécharge INSEE + OFS par défaut)")
    ap.add_argument("--insee", default=None, help="CSV INSEE local (sinon téléchargé)")
    ap.add_argument("--ofs-f", default=None, help="CSV OFS féminin local (firstname,VALUE)")
    ap.add_argument("--ofs-m", default=None, help="CSV OFS masculin local (firstname,VALUE)")
    ap.add_argument("--no-ofs", action="store_true", help="INSEE seul (pas de couverture suisse)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"sortie (défaut : {DEFAULT_OUT})")
    a = ap.parse_args()
    print(f"Écrit : {build(a.insee, a.ofs_f, a.ofs_m, a.out, with_ofs=not a.no_ofs)}")


if __name__ == "__main__":
    main()
