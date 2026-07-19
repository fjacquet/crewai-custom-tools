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


def _swiss_payload(*labels):
    return {"results": [{"attrs": {"label": f"<b>{lbl}</b>", "lat": 46.5, "lon": 6.6}}
                        for lbl in labels]}


def test_map_swiss_exact_match_scores_one_despite_canton_suffix():
    from crewai_custom_tools.tools.genealogy.geo.suisse import map_swiss
    from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace
    rp = map_swiss(_swiss_payload("Lausanne (VD)"),
                   ParsedPlace(raw="Lausanne, Vaud, Suisse", commune="Lausanne", country="Suisse"))
    assert rp is not None
    assert rp.score == 1.0
    assert rp.name == "Lausanne (VD)"
    assert rp.lat == "46.5" and rp.long == "6.6"          # WGS84 lat/lon, jamais x/y


def test_map_swiss_picks_best_not_first():
    from crewai_custom_tools.tools.genealogy.geo.suisse import map_swiss
    from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace
    # exact match is second in the list -> argmax must pick it
    rp = map_swiss(_swiss_payload("Belmont-sur-Lausanne (VD)", "Lausanne (VD)"),
                   ParsedPlace(raw="", commune="Lausanne", country="Suisse"))
    assert rp.name == "Lausanne (VD)"
    assert rp.score == 1.0


def test_resolve_ch_requests_municipalities_only(monkeypatch):
    from crewai_custom_tools.tools.genealogy.geo import suisse
    from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace
    seen = {}
    def fake_get(url, params):
        seen.update(params)
        return _swiss_payload("Lausanne (VD)")
    monkeypatch.setattr(suisse, "_http_get", fake_get)
    suisse.resolve_ch(ParsedPlace(raw="", commune="Lausanne", country="Suisse"))
    assert seen.get("origins") == "gg25"
