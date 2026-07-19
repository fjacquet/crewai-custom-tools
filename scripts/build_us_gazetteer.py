"""Build the bundled us_places.csv — the tool provisions its own data.

By default this DOWNLOADS the official US Census Bureau Gazetteer Files
"Places" national file and writes the embedded name+state → FIPS/coordinates
table used by resolve_us() (the INSEE-analog for the US):

    uv run python scripts/build_us_gazetteer.py

Source (auto-téléchargée) :
- US Census Bureau — Gazetteer Files, national Places file (2024 vintage,
  falling back to 2023 if that URL 404s). Public domain (US government work).
  Zip containing a tab-delimited file with a header row; columns include
  USPS (2-letter state), GEOID (place FIPS), NAME (official place name),
  INTPTLAT / INTPTLONG (internal-point lat/long, WGS84).
  <https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html>

Offline / test : passer --local <chemin vers le .txt déjà extrait du zip>
pour sauter le téléchargement. Voir
src/crewai_custom_tools/tools/genealogy/data/README.md pour la provenance.
"""

from __future__ import annotations

import argparse
import csv
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

GAZ_URL_2024 = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                "2024_Gazetteer/2024_Gaz_place_national.zip")
GAZ_URL_2023 = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                "2023_Gazetteer/2023_Gaz_place_national.zip")
_UA = "genecrew-build/1.0 (open data)"

DEFAULT_OUT = (Path(__file__).resolve().parents[1]
               / "src/crewai_custom_tools/tools/genealogy/data/us_places.csv")


def _fetch(url: str, dest: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())
    return dest


def download_gaz(dest_dir: Path) -> Path:
    """Download the Census Gazetteer Places national zip (2024, falling back
    to 2023 on a 404/HTTP error) and extract its tab-delimited file into dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "gaz_place_national.zip"
    try:
        _fetch(GAZ_URL_2024, zip_path)
    except urllib.error.HTTPError:
        _fetch(GAZ_URL_2023, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        zf.extract(txt_name, dest_dir)
    return dest_dir / txt_name


def _read_gaz(path: str) -> list[dict[str, str]]:
    """Parse the Gazetteer's tab-delimited file, tolerant of whitespace and delimiter.

    Header/values are stripped (the Census files sometimes pad column names).
    Delimiter is tab; sniffed as a fallback for oddly-exported variants.
    """
    with open(path, encoding="latin-1", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
        except csv.Error:
            delimiter = "\t"
        reader = csv.DictReader(fh, delimiter=delimiter)
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
                for row in reader]


def build(local: str | None = None, out: str | Path = DEFAULT_OUT) -> Path:
    """Build us_places.csv. Downloads the Gazetteer unless `local` is given."""
    with tempfile.TemporaryDirectory() as tmp:
        path = local or str(download_gaz(Path(tmp)))
        rows = _read_gaz(path)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["state", "name", "geoid", "lat", "long"])
        for row in rows:
            state, name, geoid = row.get("USPS", ""), row.get("NAME", ""), row.get("GEOID", "")
            if not (state and name and geoid):
                continue
            writer.writerow([state, name, geoid, row.get("INTPTLAT", ""), row.get("INTPTLONG", "")])
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build us_places.csv (télécharge le Census Gazetteer par défaut)")
    ap.add_argument("--local", default=None,
                     help="fichier .txt local déjà extrait du zip (sinon téléchargé)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"sortie (défaut : {DEFAULT_OUT})")
    a = ap.parse_args()
    print(f"Écrit : {build(a.local, a.out)}")


if __name__ == "__main__":
    main()
