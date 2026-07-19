# tests/test_genealogy_geo_suisse.py
from crewai_custom_tools.tools.genealogy.geo.suisse import map_swiss
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace

# forme réelle api3.geo.admin.ch SearchServer (type=locations)
PAYLOAD = {"results": [{"attrs": {
    "label": "<b>Zürich</b>", "detail": "zürich zh", "origin": "gazetteer",
    "lat": 47.3769, "lon": 8.5417,          # WGS84 (à lire)
    "x": 1247000.0, "y": 2683000.0,          # LV95 (à IGNORER)
}}]}


def test_map_swiss_reads_latlon_not_xy():
    parsed = ParsedPlace(raw="…", commune="Zürich", country="Suisse")
    rp = map_swiss(PAYLOAD, parsed)
    assert rp is not None
    assert rp.lat == "47.3769" and rp.long == "8.5417"   # jamais 1247000/2683000
    assert rp.source == "swisstopo"
    assert rp.name == "Zürich"                            # label nettoyé des <b>
    assert rp.chains[0].levels[0].name == "Suisse"
    assert 0.0 < rp.score <= 1.0
