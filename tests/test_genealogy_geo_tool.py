import json

from crewai_custom_tools.tools.genealogy.geo import tools as geo_tools
from crewai_custom_tools.tools.genealogy.geo.tools import GenealogyResolvePlaceTool
from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain,
    PlaceLevel,
    ResolvedPlace,
)

_RESOLVED = ResolvedPlace(
    name="Bourges", place_type="Commune", lat="47.081", long="2.399", code="18033",
    chains=[DatedChain(levels=[
        PlaceLevel(name="France", place_type="Country"),
        PlaceLevel(name="Cher", place_type="Department"),
        PlaceLevel(name="Bourges", place_type="Commune"),
    ])],
    score=1.0, source="geo.api.gouv.fr", query="Bourges, Cher, France",
)


def test_resolve_place_authoritative_ecrire(mocker):
    mocker.patch.object(geo_tools, "resolve_place", return_value=_RESOLVED)
    data = json.loads(GenealogyResolvePlaceTool()._run(raw="Bourges, Cher, France"))
    assert data["success"] is True
    d = data["data"]
    assert d["pays"] == "France" and d["commune"] == "Bourges"
    assert d["action"] == "ecrire"
    assert d["resolved"]["code"] == "18033" and d["resolved"]["lat"] == "47.081"
    assert d["resolved"]["source"] == "geo.api.gouv.fr"


def test_resolve_place_unresolved_is_indecidable(mocker):
    mocker.patch.object(geo_tools, "resolve_place", return_value=None)
    data = json.loads(GenealogyResolvePlaceTool()._run(raw="Xyzzy, Nulle-Part"))
    assert data["success"] is True
    assert data["data"]["action"] == "indecidable"
    assert data["data"]["resolved"] is None


def test_resolve_place_low_score_is_proposition(mocker):
    low = _RESOLVED.model_copy(update={"score": 0.7, "source": "Nominatim/OSM"})
    mocker.patch.object(geo_tools, "resolve_place", return_value=low)
    data = json.loads(GenealogyResolvePlaceTool()._run(raw="Bourges", min_score=0.9))
    assert data["data"]["action"] == "proposition"
