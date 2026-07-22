import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import (
    GrampsCreatePlaceTool,
    date_qualifier_to_gramps_date,
)

CONFIG = GrampsConfig(api_url="http://g.test/api", username="u", password="p")


@pytest.fixture(autouse=True)
def _no_global_dry_run(monkeypatch):
    monkeypatch.setenv("GENECREW_DRY_RUN", "false")


def test_date_qualifier_before_after_none():
    assert date_qualifier_to_gramps_date("avant 1962-07-05") == {
        "_class": "Date", "modifier": 1, "dateval": [5, 7, 1962, False]}
    assert date_qualifier_to_gramps_date("après 1962-07-05")["modifier"] == 2
    assert date_qualifier_to_gramps_date(None) is None
    assert date_qualifier_to_gramps_date("n'importe quoi") is None


def test_create_place_parent_placeref_carries_gramps_date(mocker):
    posts = []

    def handler(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        if request.method == "POST" and request.url.path == "/api/places/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json={"handle": "H"})
        return httpx.Response(404)

    mocker.patch.object(write_tools, "get_client",
                        return_value=GrampsClient(CONFIG, transport=httpx.MockTransport(handler)))
    GrampsCreatePlaceTool()._run(name="Alger", place_type="Municipality",
                                 parent_handle="H_DZ", date_qualifier="après 1962-07-05")
    ref = posts[0]["placeref_list"][0]
    assert ref["ref"] == "H_DZ"
    assert ref["date"] == {"_class": "Date", "modifier": 2, "dateval": [5, 7, 1962, False]}
    assert "_date_qualifier" not in ref                # remplacé par une vraie Date
