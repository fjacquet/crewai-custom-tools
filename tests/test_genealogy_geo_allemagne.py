import sys
from pathlib import Path

from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_build_parse_rows_derives_ags_and_point():
    import build_de_gazetteer as b
    sample = ('gem_code;gem_name_short;gem_name;lan_name;geo_point_2d\n'
              '146270060060;["Großenhain"];["Stadt Großenhain"];["Sachsen"];51.3237,13.5230\n')
    rows = list(b.parse_rows(sample))
    assert rows == [{"ags": "14627060", "name": "Großenhain", "land": "Sachsen",
                     "lat": "51.3237", "long": "13.5230"}]


# --- Résolveur (Task 3) : gazetteer injecté, offline ---
FIX = {
    "by_ags": {"06635021": {"name": "Waldeck", "land": "Hessen", "ags": "06635021",
                            "lat": "51.2049", "long": "9.0653"}},
    "by_name": {"WALDECK": [
        {"name": "Waldeck", "land": "Hessen", "ags": "06635021", "lat": "51.2049", "long": "9.0653"},
        {"name": "Waldeck", "land": "Thüringen", "ags": "16062037", "lat": "50.79", "long": "11.29"},
    ], "GROSSENHAIN": [
        {"name": "Großenhain", "land": "Sachsen", "ags": "14627060", "lat": "51.32", "long": "13.52"}]},
}


def test_resolve_de_by_ags_is_authoritative():
    from crewai_custom_tools.tools.genealogy.geo.allemagne import resolve_de
    p = ParsedPlace(raw="", commune="Waldeck", country="Allemagne", ags="06635021", region="Hesse")
    rp = resolve_de(p, table=FIX)
    assert rp is not None and rp.score == 1.0 and rp.ambiguous is False
    assert rp.code == "06635021" and rp.lat == "51.2049" and rp.long == "9.0653"
    assert [lvl.name for lvl in rp.chains[0].levels] == ["Allemagne", "Hessen"]


def test_resolve_de_homonym_without_land_is_proposition():
    from crewai_custom_tools.tools.genealogy.geo.allemagne import resolve_de
    p = ParsedPlace(raw="", commune="Waldeck", country="Allemagne")
    rp = resolve_de(p, table=FIX)
    assert rp is not None and rp.ambiguous is True     # Waldeck Hesse vs Thuringe


def test_resolve_de_name_plus_land_alias_disambiguates():
    from crewai_custom_tools.tools.genealogy.geo.allemagne import resolve_de
    # 'Hesse' (FR) doit matcher le Land 'Hessen' (DE) du gazetteer
    p = ParsedPlace(raw="", commune="Waldeck", country="Allemagne", region="Hesse")
    rp = resolve_de(p, table=FIX)
    assert rp is not None and rp.ambiguous is False and rp.code == "06635021"   # Hesse, pas Thuringe


def test_resolve_de_unknown_name_returns_none():
    from crewai_custom_tools.tools.genealogy.geo.allemagne import resolve_de
    p = ParsedPlace(raw="", commune="Nowhere", country="Allemagne")
    assert resolve_de(p, table=FIX) is None


def test_norm_de_umlaut_and_eszett():
    from crewai_custom_tools.tools.genealogy.geo.allemagne import _norm_de
    assert _norm_de("Großenhain") == _norm_de("Grossenhain")
    assert _norm_de("München") == _norm_de("Muenchen")
