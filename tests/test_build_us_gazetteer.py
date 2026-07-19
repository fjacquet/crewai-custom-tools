"""Test hors-ligne du build de la table us_places (fixture tab-delimited, sans réseau).

Passe --local, donc download_gaz() n'est jamais appelé.
"""

import csv

from build_us_gazetteer import build


def _rows(out):
    return {r["name"]: r for r in csv.DictReader(open(out, encoding="utf-8"))}


def test_build_parses_tab_delimited_sample(tmp_path):
    sample = tmp_path / "2024_gaz_place_national.txt"
    sample.write_text(
        "USPS\tGEOID\tANSICODE\tNAME\tLSAD\tFUNCSTAT\tALAND\tAWATER"
        "\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG\n"
        "IL\t1772000\t0428803\tSpringfield\t25\tA\t159621501\t2437461"
        "\t61.630\t0.941\t39.7817\t-89.6501\n"
        "NY\t3651000\t0979587\tNew York\t25\tA\t780052442\t429969783"
        "\t301.267\t166.011\t40.6635\t-73.9387\n",
        encoding="utf-8",
    )
    out = tmp_path / "us_places.csv"
    build(local=str(sample), out=out)
    rows = _rows(out)
    assert rows["Springfield"]["state"] == "IL"
    assert rows["Springfield"]["geoid"] == "1772000"
    assert rows["Springfield"]["lat"] == "39.7817"
    assert rows["Springfield"]["long"] == "-89.6501"
    assert rows["New York"]["state"] == "NY" and rows["New York"]["geoid"] == "3651000"


def test_build_tolerates_padded_header_whitespace(tmp_path):
    # Some Census exports pad header names with stray whitespace — the reader must strip them.
    sample = tmp_path / "sample.txt"
    sample.write_text(
        " USPS \t GEOID \t NAME \t INTPTLAT \t INTPTLONG \n"
        "CA\t0668000\tLos Angeles\t34.0194\t-118.4108\n",
        encoding="utf-8",
    )
    out = tmp_path / "us_places.csv"
    build(local=str(sample), out=out)
    rows = _rows(out)
    assert rows["Los Angeles"]["state"] == "CA"
    assert rows["Los Angeles"]["geoid"] == "0668000"
