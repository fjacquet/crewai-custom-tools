# crewai_custom_tools/tests/test_genealogy_places_models.py
from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain,
    DatedName,
    PlaceLevel,
    PlaceMergeProposition,
    PlaceProposition,
    ResolvedPlace,
)


def test_resolved_place_defaults_single_chain_roundtrip():
    rp = ResolvedPlace(
        name="Bourges", place_type="Municipality", lat="47.081", long="2.399",
        code="18033",
        chains=[DatedChain(levels=[
            PlaceLevel(name="France", place_type="Country"),
            PlaceLevel(name="Centre-Val de Loire", place_type="Region"),
            PlaceLevel(name="Cher", place_type="Department", code="18"),
        ])],
        alt_names=[DatedName(value=", , Bourges, 18033, 18000, Cher, ...")],
        score=1.0, source="geo.api.gouv.fr", query="/communes/18033",
    )
    assert rp.chains[0].date_qualifier is None      # P1-P4 : chaîne unique non datée
    assert rp.ambiguous is False                    # garde-fou d'ambiguïté, défaut
    assert ResolvedPlace(**rp.model_dump()) == rp   # round-trip


def test_parsed_place_and_propositions_roundtrip():
    pp = PlaceProposition(
        type="lieu_resolu", gramps_id="I0501", handle="h1",
        original=", , Bourges, 18033, 18000, Cher, Centre-Val de Loire, France",
        country="France", resolution=None, action="proposition",
        confiance="basse", priorite="moyenne", preuve="…",
    )
    assert PlaceProposition(**pp.model_dump()) == pp
    mp = PlaceMergeProposition(gramps_id_keep="I0501", handle_keep="h1",
                               gramps_id_merge="I0733", handle_merge="h2",
                               canonical="Bourges", reason="même commune canonique")
    assert PlaceMergeProposition(**mp.model_dump()) == mp
