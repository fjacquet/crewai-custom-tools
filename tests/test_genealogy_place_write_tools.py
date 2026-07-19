import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.write_tools import (
    GrampsCreatePlaceTool, GrampsUpdatePlaceTool,
)

CONFIG = GrampsConfig(api_url="http://g.test/api", username="u", password="p")


@pytest.fixture(autouse=True)
def _no_global_dry_run(monkeypatch):
    monkeypatch.setenv("GENECREW_DRY_RUN", "false")


def _client(on_put=None, on_post=None, existing=None):
    def handler(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        if request.method == "GET" and request.url.path.startswith("/api/places/"):
            return httpx.Response(200, json=existing or {})
        if request.method == "POST" and request.url.path == "/api/places/":
            return on_post(request) if on_post else httpx.Response(
                201, json=[{"type": "add", "_class": "Place", "handle": "NEW"}])
        if request.method == "PUT":
            return on_put(request) if on_put else httpx.Response(200, json={})
        return httpx.Response(404)
    return GrampsClient(CONFIG, transport=httpx.MockTransport(handler))


def test_create_place_dry_run_returns_synthetic_handle(mocker):
    mocker.patch.object(write_tools, "get_client", return_value=_client())
    data = json.loads(GrampsCreatePlaceTool()._run(name="France", place_type="Country", dry_run=True))
    assert data["success"] is True
    assert data["data"]["handle"] == "DRYRUN:France"     # handle synthétique, aucun POST


def test_create_place_writes_and_returns_handle(mocker):
    posts = []

    def on_post(request):
        posts.append(json.loads(request.content))
        # Gramps Web returns a 201 transaction ARRAY, not a {"handle": ...} dict:
        return httpx.Response(201, json=[{"type": "add", "_class": "Place", "handle": "H_FR"}])

    mocker.patch.object(write_tools, "get_client", return_value=_client(on_post=on_post))
    data = json.loads(GrampsCreatePlaceTool()._run(name="France", place_type="Country"))
    assert data["data"]["handle"] == "H_FR" and len(posts) == 1   # handle read from the array
    assert posts[0]["place_type"] == "Country"
    assert posts[0]["handle"]                                     # a client handle was also sent


def test_create_place_falls_back_to_client_handle_when_response_has_none(mocker):
    posts = []

    def on_post(request):
        posts.append(json.loads(request.content))
        return httpx.Response(201, json=[])           # server returns no parseable handle

    mocker.patch.object(write_tools, "get_client", return_value=_client(on_post=on_post))
    data = json.loads(GrampsCreatePlaceTool()._run(name="France", place_type="Country"))
    assert data["data"]["handle"] == posts[0]["handle"]   # falls back to the handle we sent
    assert data["data"]["handle"] and data["data"]["created"] is True


def test_created_handle_extracts_from_transaction_array():
    from crewai_custom_tools.tools.genealogy.gramps.write_tools import _created_handle
    assert _created_handle([{"type": "add", "_class": "Place", "handle": "H1"}]) == "H1"
    assert _created_handle([{"type": "add", "new": {"handle": "H2"}}]) == "H2"
    assert _created_handle([]) is None
    assert _created_handle({"handle": "H3"}) == "H3"      # tolerate a bare dict too
    assert _created_handle(None) is None


def test_update_place_noop_when_conforming(mocker):
    existing = {"handle": "h1", "gramps_id": "P1", "name": {"value": "Bourges"},
                "place_type": "Municipality", "lat": "47.081", "long": "2.399",
                "placeref_list": [{"ref": "H_CHER"}], "alt_names": []}

    def on_put(request):
        raise AssertionError("no PUT expected when already conforming")

    mocker.patch.object(write_tools, "get_client", return_value=_client(on_put=on_put, existing=existing))
    data = json.loads(GrampsUpdatePlaceTool()._run(
        handle="h1", name="Bourges", place_type="Municipality", lat="47.081", long="2.399",
        placeref_list=[{"ref": "H_CHER"}]))
    assert data["data"]["noop"] is True


def test_update_place_code_only_change_fires_put(mocker):
    existing = {"handle": "h1", "gramps_id": "P1", "name": {"value": "Bourges"},
                "place_type": "Municipality", "lat": "47.081", "long": "2.399",
                "code": "18033", "placeref_list": [{"ref": "H_CHER"}], "alt_names": []}
    puts = []

    def on_put(request):
        puts.append(json.loads(request.content))
        return httpx.Response(200, json={})

    mocker.patch.object(write_tools, "get_client",
                        return_value=_client(on_put=on_put, existing=existing))
    data = json.loads(GrampsUpdatePlaceTool()._run(
        handle="h1", name="Bourges", place_type="Municipality", lat="47.081", long="2.399",
        code="18099",                                  # differs from stored 18033
        placeref_list=[{"ref": "H_CHER"}]))
    assert data["data"]["noop"] is False               # NOT a no-op
    assert len(puts) == 1 and puts[0]["code"] == "18099"


def test_update_place_altnames_deduped_within_call(mocker):
    existing = {"handle": "h1", "gramps_id": "P1", "name": {"value": "Bourges"},
                "place_type": "Municipality", "placeref_list": [], "alt_names": []}
    puts = []

    def on_put(request):
        puts.append(json.loads(request.content))
        return httpx.Response(200, json={})

    mocker.patch.object(write_tools, "get_client",
                        return_value=_client(on_put=on_put, existing=existing))
    GrampsUpdatePlaceTool()._run(handle="h1", name="Bourges", place_type="Municipality",
                                 alt_names=[{"value": "Avaricum"}, {"value": "Avaricum"}])
    values = [a["value"] for a in puts[0]["alt_names"]]
    assert values.count("Avaricum") == 1               # appended once, not twice
