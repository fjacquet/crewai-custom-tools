import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import (
    GrampsAttachCitationTool,
    GrampsCreateCitationTool,
    GrampsEnsureSourceTool,
)

CONFIG = GrampsConfig(api_url="http://g.test/api", username="u", password="p")


@pytest.fixture(autouse=True)
def _no_global_dry_run(monkeypatch):
    monkeypatch.setenv("GENECREW_DRY_RUN", "false")


def _client(handler):
    def _h(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        return handler(request)
    return GrampsClient(CONFIG, transport=httpx.MockTransport(_h))


# --- EnsureSource (idempotent) ---

def test_ensure_source_returns_existing(mocker):
    posts = []

    def h(request):
        if request.method == "GET" and request.url.path == "/api/sources/":
            page = int(request.url.params.get("page"))
            return httpx.Response(200, json=[
                {"title": "INSEE — Fichier des personnes décédées",
                 "handle": "SRC1"}] if page == 1 else [])
        if request.method == "POST":
            posts.append(request.url.path)
            return httpx.Response(201, json=[{"handle": "X"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsEnsureSourceTool()._run(
        title="INSEE — Fichier des personnes décédées"))
    assert data["data"]["handle"] == "SRC1" and data["data"]["created"] is False
    assert posts == []


def test_ensure_source_creates_when_absent(mocker):
    def h(request):
        if request.method == "GET" and request.url.path == "/api/sources/":
            page = int(request.url.params.get("page"))
            return httpx.Response(200, json=[{"title": "Autre", "handle": "S0"}]
                                  if page == 1 else [])
        if request.method == "POST" and request.url.path == "/api/sources/":
            body = json.loads(request.content)
            assert body["title"] == "INSEE — Fichier des personnes décédées"
            assert body["author"] == "INSEE"
            return httpx.Response(201, json=[
                {"type": "add", "_class": "Source", "handle": "SRC_NEW"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsEnsureSourceTool()._run(
        title="INSEE — Fichier des personnes décédées", author="INSEE"))
    assert data["data"]["handle"] == "SRC_NEW" and data["data"]["created"] is True


# --- CreateCitation ---

def test_create_citation_posts_and_caps_confidence(mocker):
    posts = []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/citations/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json=[{"type": "add", "handle": "CIT1"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreateCitationTool()._run(
        source_handle="SRC1", page="fichier INSEE 2021, ligne 610579, acte 1511",
        confidence=4))                                        # tentative au-dessus du plafond
    assert data["data"]["handle"] == "CIT1"
    assert posts[0]["confidence"] == 2                        # plafond IA garanti
    assert posts[0]["source_handle"] == "SRC1"
    assert "acte 1511" in posts[0]["page"]


def test_create_citation_dry_run_and_dryrun_source(mocker):
    def h(request):
        raise AssertionError("aucun POST attendu")
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreateCitationTool()._run(
        source_handle="DRYRUN:source", page="x"))
    assert data["data"]["handle"] == "DRYRUN:citation" and data["data"]["dry_run"] is True


# --- AttachCitation (append-only) ---

_EVENT = {"_class": "Event", "handle": "EV1", "gramps_id": "E0607",
          "citation_list": ["C_OLD"], "type": "Death",
          "date": {"year": 2021}}


def test_attach_citation_appends_only_citation_list(mocker):
    puts = []

    def h(request):
        if request.method == "GET" and request.url.path == "/api/events/EV1":
            return httpx.Response(200, json=_EVENT)
        if request.method == "PUT" and request.url.path == "/api/events/EV1":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsAttachCitationTool()._run(
        object_type="events", handle="EV1", citation_handle="CIT1"))
    assert data["data"]["changed"] is True
    put = puts[0]
    assert put["citation_list"] == ["C_OLD", "CIT1"]          # append, pas d'écrasement
    for k in ("type", "date", "gramps_id", "_class"):
        assert put[k] == _EVENT[k]                            # invariant append-only


def test_attach_citation_dedups_and_dry_run(mocker):
    puts = []

    def h(request):
        if request.method == "GET" and request.url.path == "/api/events/EV1":
            return httpx.Response(200, json=_EVENT)
        if request.method == "PUT":
            puts.append(request.url.path)
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    already = json.loads(GrampsAttachCitationTool()._run(
        object_type="events", handle="EV1", citation_handle="C_OLD"))
    assert already["data"]["changed"] is False
    dry = json.loads(GrampsAttachCitationTool()._run(
        object_type="events", handle="EV1", citation_handle="CIT9", dry_run=True))
    assert dry["data"]["changed"] is True and dry["data"]["dry_run"] is True
    assert puts == []                                         # rien écrit
