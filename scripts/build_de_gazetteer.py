"""Provision the embedded German municipality gazetteer from OpenDataSoft (BKG VG250).

Downloads georef-germany-gemeinde and writes data/de_communes.csv (ags,name,land,lat,long).
Run: uv run python scripts/build_de_gazetteer.py [--local downloaded.csv]
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

import httpx

URL = ("https://data.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
       "georef-germany-gemeinde@public/exports/csv?delimiter=%3B&use_labels=false"
       "&select=gem_code,gem_name_short,gem_name,lan_name,geo_point_2d")
OUT = Path(__file__).resolve().parents[1] / \
    "src/crewai_custom_tools/tools/genealogy/data/de_communes.csv"


def _first(v: str) -> str:
    """OpenDataSoft array-ish field -> first value ('["Hessen"]' or 'Hessen' -> 'Hessen')."""
    v = (v or "").strip().strip("[]")
    return v.split(",")[0].strip().strip('"').strip()


def ags_from_ars(ars: str) -> str:
    """8-digit AGS from the 12-digit ARS: Land+RB+Kreis (5) + Gemeinde (last 3)."""
    ars = "".join(ch for ch in ars if ch.isdigit())
    return ars[:5] + ars[-3:] if len(ars) >= 8 else ars


def parse_rows(text: str):
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";")   # strip BOM
    for r in reader:
        ars = _first(r.get("gem_code", ""))
        name = _first(r.get("gem_name_short", "")) or _first(r.get("gem_name", ""))
        land = _first(r.get("lan_name", ""))
        pt = (r.get("geo_point_2d", "") or "").strip()          # "lat,lon"
        if not (ars and name and pt and "," in pt):
            continue
        lat, lon = (x.strip() for x in pt.split(",", 1))
        yield {"ags": ags_from_ars(ars), "name": name, "land": land, "lat": lat, "long": lon}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", type=Path, help="parse a local CSV instead of downloading")
    args = ap.parse_args()
    if args.local:
        text = args.local.read_text(encoding="utf-8")
    else:
        resp = httpx.get(URL, timeout=180.0, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
    rows = list(parse_rows(text))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ags", "name", "land", "lat", "long"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} : {len(rows)} communes")


if __name__ == "__main__":
    main()
