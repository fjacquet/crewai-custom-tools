# tests/test_genealogy_geo_nominatim.py
from crewai_custom_tools.tools.genealogy.geo.nominatim import map_nominatim
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace

RESULTS = [
    {"display_name": "Alger, Algérie", "lat": "36.7538", "lon": "3.0588", "importance": 0.82},
    {"display_name": "Alger (autre)", "lat": "0", "lon": "0", "importance": 0.40},
]


def test_map_nominatim_score_and_gps():
    parsed = ParsedPlace(raw="…", commune="Alger", country="Algérie")
    rp = map_nominatim(RESULTS, parsed)
    assert rp.lat == "36.7538" and rp.long == "3.0588"
    assert rp.source == "Nominatim/OSM"
    assert 0.0 < rp.score <= 1.0
    assert rp.ambiguous is False           # 0.82 vs 0.40 top-conf → marge large
    assert rp.chains[0].levels[0].name == "Algérie"   # pays parent depuis parsed.country


def test_map_nominatim_empty_returns_none():
    assert map_nominatim([], ParsedPlace(raw="x", commune="Nowhere")) is None
