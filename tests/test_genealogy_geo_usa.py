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


def test_find_state_prefers_region_over_county_homonym():
    # US counties are commonly named after states (Washington/Delaware County),
    # so a blind left-to-right token scan of `raw` lets the county hijack the
    # state. The parser already puts the STATE in `parsed.region` and the
    # county in `parsed.departement` — _find_state must prefer that.
    from crewai_custom_tools.tools.genealogy.geo.usa import _find_state

    p = ParsedPlace(raw=", , Marietta, , , Washington, Ohio, États-Unis",
                     commune="Marietta", departement="Washington", region="Ohio",
                     country="États-Unis")
    assert _find_state(p) == "OH"          # NOT "WA" (Washington County)
    p2 = ParsedPlace(raw=", , Sunbury, , , Delaware, Ohio, États-Unis",
                      commune="Sunbury", departement="Delaware", region="Ohio",
                      country="États-Unis")
    assert _find_state(p2) == "OH"         # NOT "DE" (Delaware County)


def test_resolve_us_county_homonym_resolves_correct_state():
    # With a fixture table keyed on ("SUNBURY", "OH"), the Delaware-county
    # string must still resolve to OH, not be hijacked into a DE lookup.
    table = {("SUNBURY", "OH"): {"name": "Sunbury", "geoid": "3975098",
                                  "lat": "40.2428", "long": "-82.8546"}}
    p = ParsedPlace(raw=", , Sunbury, , , Delaware, Ohio, États-Unis", commune="Sunbury",
                     departement="Delaware", region="Ohio", country="États-Unis")
    rp = resolve_us(p, table=table)
    assert rp is not None and rp.name == "Sunbury"


def test_load_us_gazetteer_marks_collision_ambiguous(tmp_path):
    # Two Census rows sharing the same (state, stripped-name) key must not
    # silently overwrite each other — the surviving entry is marked ambiguous
    # so resolve_us reports a proposition, not a confident wrong write.
    csv_path = tmp_path / "us_places.csv"
    csv_path.write_text(
        "state,name,geoid,lat,long\n"
        "OH,Springfield city,1234567,39.0,-83.0\n"
        "OH,Springfield village,7654321,40.0,-84.0\n",
        encoding="utf-8",
    )
    table = load_us_gazetteer(path=csv_path)
    entry = table[("SPRINGFIELD", "OH")]
    assert entry["ambiguous"] is True
    # First row's data is kept, not silently replaced by the second.
    assert entry["name"] == "Springfield city" and entry["geoid"] == "1234567"


def test_load_us_gazetteer_non_colliding_entry_not_ambiguous(tmp_path):
    csv_path = tmp_path / "us_places.csv"
    csv_path.write_text(
        "state,name,geoid,lat,long\n"
        "IL,Springfield city,1772000,39.791063,-89.644572\n",
        encoding="utf-8",
    )
    table = load_us_gazetteer(path=csv_path)
    assert table[("SPRINGFIELD", "IL")]["ambiguous"] is False


def test_resolve_us_propagates_ambiguous_from_table_entry():
    table = {("SPRINGFIELD", "IL"): {"name": "Springfield", "geoid": "1772000",
                                      "lat": "39.7817", "long": "-89.6501",
                                      "ambiguous": True}}
    parsed = ParsedPlace(raw=", , Springfield, , , Sangamon, Illinois, États-Unis",
                          commune="Springfield", departement="Sangamon", region="Illinois",
                          country="États-Unis")
    rp = resolve_us(parsed, table=table)
    assert rp is not None and rp.ambiguous is True
