# tests/test_genealogy_geo_usa.py
"""Offline tests for the US resolver (fixture table injected, no network)."""

from crewai_custom_tools.tools.genealogy.geo.usa import load_us_gazetteer, resolve_us
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace

FIXTURE = {("SPRINGFIELD", "IL"): {"name": "Springfield", "geoid": "1772000",
                                    "lat": "39.7817", "long": "-89.6501"}}


def test_resolve_us_by_name_and_state_full_name():
    parsed = ParsedPlace(raw=", , Springfield, , , Sangamon, Illinois, États-Unis",
                          commune="Springfield", departement="Sangamon", country="États-Unis")
    rp = resolve_us(parsed, table=FIXTURE)
    assert rp is not None
    assert rp.name == "Springfield" and rp.code == "1772000"
    assert rp.lat == "39.7817" and rp.long == "-89.6501"
    levels = [lvl.name for lvl in rp.chains[0].levels]
    assert levels[0] == "États-Unis" and "Illinois" in levels and "Sangamon" in levels
    assert rp.source == "US Census Gazetteer" and 0 < rp.score <= 1.0


def test_resolve_us_state_abbreviation():
    parsed = ParsedPlace(raw=", , Springfield, , , Sangamon, IL, États-Unis",
                          commune="Springfield", departement="Sangamon", country="États-Unis")
    rp = resolve_us(parsed, table=FIXTURE)
    assert rp is not None
    assert rp.name == "Springfield" and rp.code == "1772000"


def test_resolve_us_none_when_absent():
    parsed = ParsedPlace(raw=", , Chicago, , , Cook, Illinois, États-Unis",
                          commune="Chicago", departement="Cook", country="États-Unis")
    assert resolve_us(parsed, table=FIXTURE) is None


def test_resolve_us_none_when_no_state():
    parsed = ParsedPlace(raw=", , Springfield, , , , , États-Unis",
                          commune="Springfield", country="États-Unis")
    assert resolve_us(parsed, table=FIXTURE) is None


def test_load_us_gazetteer_strips_lsad_suffix_for_lookup(tmp_path):
    # Real Census NAME values carry a trailing legal/statistical descriptor
    # ("Springfield city") that a genealogy string's bare commune name never
    # does — the lookup key must strip it while the display name keeps it.
    csv_path = tmp_path / "us_places.csv"
    csv_path.write_text(
        "state,name,geoid,lat,long\n"
        "IL,Springfield city,1772000,39.791063,-89.644572\n"
        "AR,Georgetown town,0526440,35.126678,-91.453923\n",
        encoding="utf-8",
    )
    table = load_us_gazetteer(path=csv_path)
    assert table[("SPRINGFIELD", "IL")]["name"] == "Springfield city"
    assert table[("GEORGETOWN", "AR")]["name"] == "Georgetown town"


def test_resolve_us_matches_bare_commune_against_suffixed_gazetteer_entry(tmp_path):
    csv_path = tmp_path / "us_places.csv"
    csv_path.write_text(
        "state,name,geoid,lat,long\n"
        "IL,Springfield city,1772000,39.791063,-89.644572\n",
        encoding="utf-8",
    )
    table = load_us_gazetteer(path=csv_path)
    parsed = ParsedPlace(raw=", , Springfield, , , Sangamon, Illinois, États-Unis",
                          commune="Springfield", departement="Sangamon", country="États-Unis")
    rp = resolve_us(parsed, table=table)
    assert rp is not None
    assert rp.name == "Springfield city" and rp.code == "1772000"
    # An exact (name, state) key match is authoritative — the LSAD suffix
    # ("city") is a naming convention, not fuzzy-match uncertainty, so an
    # otherwise-exact commune match must still score a full 1.0.
    assert rp.score == 1.0
