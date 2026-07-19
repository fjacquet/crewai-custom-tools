# tests/test_genealogy_geo_france.py
from crewai_custom_tools.tools.genealogy.geo.france import map_commune, resolve_fr
from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace

# forme réelle de geo.api.gouv.fr/communes/{code}?fields=nom,centre,codeDepartement,...
PAYLOAD = {
    "nom": "Bourges", "code": "18033",
    "centre": {"type": "Point", "coordinates": [2.3992, 47.0810]},   # [lon, lat]
    "codeDepartement": "18", "codeRegion": "24",
    "departement": {"code": "18", "nom": "Cher"},
    "region": {"code": "24", "nom": "Centre-Val de Loire"},
}


def test_map_commune_wgs84_lonlat_and_hierarchy():
    parsed = ParsedPlace(raw="…", commune="Bourges", insee="18033", country="France")
    rp = map_commune(PAYLOAD, parsed)
    assert rp.name == "Bourges" and rp.place_type == "Municipality"
    assert rp.lat == "47.081" and rp.long == "2.3992"        # centre = [lon, lat] → long=lon, lat=lat
    assert rp.score == 1.0 and rp.source == "geo.api.gouv.fr"
    assert len(rp.chains) == 1 and rp.chains[0].date_qualifier is None
    names = [lvl.name for lvl in rp.chains[0].levels]
    assert names == ["France", "Centre-Val de Loire", "Cher"]   # haut→bas
    assert rp.alt_names[0].value == parsed.raw and rp.alt_names[0].date_qualifier is None


def test_resolve_fr_returns_none_without_insee(monkeypatch):
    parsed = ParsedPlace(raw="…", commune="X", insee=None, country="France", shifted=True)
    assert resolve_fr(parsed) is None                          # délègue au repli flou
