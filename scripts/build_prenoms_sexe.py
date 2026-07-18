"""Build the bundled prenoms_sexe.csv from INSEE + OFS source files (offline).

Run once, by hand, after downloading the official sources (see
src/crewai_custom_tools/tools/genealogy/data/README.md):

    uv run python scripts/build_prenoms_sexe.py \
        --insee nat.csv --ofs-f ofs_feminin.csv --ofs-m ofs_masculin.csv \
        --out src/crewai_custom_tools/tools/genealogy/data/prenoms_sexe.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from crewai_custom_tools.tools.genealogy.analysis.gender import normkey

RARE = "_PRENOMS_RARES"


def _add(table: dict[str, tuple[int, int]], key: str, n_f: int = 0, n_m: int = 0) -> None:
    f, m = table.get(key, (0, 0))
    table[key] = (f + n_f, m + n_m)


def _read_insee(path: str, table: dict[str, tuple[int, int]]) -> None:
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            name = row["preusuel"]
            if name == RARE:
                continue
            key = normkey(name)
            if not key:
                continue
            nombre = int(row["nombre"])
            if row["sexe"] == "1":
                _add(table, key, n_m=nombre)
            elif row["sexe"] == "2":
                _add(table, key, n_f=nombre)


def _read_ofs(path: str, table: dict[str, tuple[int, int]], *, female: bool) -> None:
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            key = normkey(row["prenom"])
            if not key:
                continue
            nombre = int(row["nombre"])
            if female:
                _add(table, key, n_f=nombre)
            else:
                _add(table, key, n_m=nombre)


def build(insee: str, ofs_f: str, ofs_m: str, out: str) -> Path:
    table: dict[str, tuple[int, int]] = {}
    _read_insee(insee, table)
    _read_ofs(ofs_f, table, female=True)
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
    ap = argparse.ArgumentParser(description="Build prenoms_sexe.csv (INSEE+OFS)")
    ap.add_argument("--insee", required=True)
    ap.add_argument("--ofs-f", required=True)
    ap.add_argument("--ofs-m", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print(f"Écrit : {build(a.insee, a.ofs_f, a.ofs_m, a.out)}")


if __name__ == "__main__":
    main()
