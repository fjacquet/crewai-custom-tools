"""Tests for the URL/media write tools (shipped in 0.17.0 without coverage)."""

import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import (
    GrampsAddUrlTool,
    GrampsAttachMediaTool,
    GrampsUploadMediaTool,
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


def _place(**extra):
    return {"handle": "P1", "gramps_id": "P0001", **extra}


# --- GrampsAddUrlTool ---

def test_add_url_appends_and_writes(mocker):
    puts = []

    def h(request):
        if request.method == "GET":
            return httpx.Response(200, json=_place(urls=[]))
        if request.method == "PUT":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsAddUrlTool()._run(
        object_type="places", handle="P1",
        url="https://fr.wikipedia.org/wiki/Lyon", description="Wikipédia"))

    assert data["success"] is True
    assert data["data"]["changed"] is True
    assert len(puts) == 1
    assert puts[0]["urls"] == [{
        "_class": "Url", "path": "https://fr.wikipedia.org/wiki/Lyon",
        "desc": "Wikipédia", "type": "Web Home"}]


def test_add_url_skips_duplicate_path(mocker):
    puts = []

    def h(request):
        if request.method == "GET":
            return httpx.Response(200, json=_place(
                urls=[{"path": "https://fr.wikipedia.org/wiki/Lyon"}]))
        puts.append(request.method)
        return httpx.Response(200, json={})
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsAddUrlTool()._run(
        object_type="places", handle="P1", url="https://fr.wikipedia.org/wiki/Lyon"))

    assert data["data"]["changed"] is False
    assert puts == []


def test_add_url_dry_run_does_not_write(mocker):
    puts = []

    def h(request):
        if request.method == "GET":
            return httpx.Response(200, json=_place(urls=[]))
        puts.append(request.method)
        return httpx.Response(200, json={})
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsAddUrlTool()._run(
        object_type="places", handle="P1", url="https://x.test/a", dry_run=True))

    assert data["data"] == {"handle": "P1", "gramps_id": "P0001",
                            "changed": True, "dry_run": True}
    assert puts == []


# --- GrampsAttachMediaTool ---

def test_attach_media_appends_ref(mocker):
    puts = []

    def h(request):
        if request.method == "GET":
            return httpx.Response(200, json=_place(media_list=[]))
        if request.method == "PUT":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsAttachMediaTool()._run(
        object_type="places", handle="P1", media_handle="M1"))

    assert data["data"]["changed"] is True
    assert puts[0]["media_list"] == [{"_class": "MediaRef", "ref": "M1"}]


def test_attach_media_refuses_dryrun_handle(mocker):
    """A DRYRUN: handle from a simulated upload must never be written as a real ref."""
    puts = []

    def h(request):
        if request.method == "GET":
            return httpx.Response(200, json=_place(media_list=[]))
        puts.append(request.method)
        return httpx.Response(200, json={})
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsAttachMediaTool()._run(
        object_type="places", handle="P1", media_handle="DRYRUN:media"))

    assert data["data"]["changed"] is False
    assert puts == []


# --- GrampsUploadMediaTool ---

def test_upload_media_dry_run_skips_download(mocker):
    get = mocker.patch("requests.get")
    data = json.loads(GrampsUploadMediaTool()._run(
        file_url="https://x.test/a.jpg", description="d", dry_run=True))

    assert data["data"] == {"handle": "DRYRUN:media", "created": False, "dry_run": True}
    get.assert_not_called()


def test_upload_media_creates_and_sets_description(mocker):
    mocker.patch("requests.get", return_value=mocker.Mock(
        content=b"\xff\xd8jpeg", headers={"Content-Type": "image/jpeg"},
        raise_for_status=mocker.Mock()))
    puts = []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/media/":
            return httpx.Response(201, json=[{"handle": "M9"}])
        if request.method == "GET":
            return httpx.Response(200, json={"handle": "M9", "mime": "image/jpeg"})
        if request.method == "PUT":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsUploadMediaTool()._run(
        file_url="https://x.test/a.jpg", description="Lyon — CC-BY"))

    assert data["data"] == {"handle": "M9", "created": True,
                            "dry_run": False, "mime": "image/jpeg"}
    assert puts[0]["desc"] == "Lyon — CC-BY"


def test_upload_media_errors_when_no_handle_returned(mocker):
    mocker.patch("requests.get", return_value=mocker.Mock(
        content=b"x", headers={"Content-Type": "image/jpeg"},
        raise_for_status=mocker.Mock()))

    def h(request):
        if request.method == "POST":
            return httpx.Response(201, json=[])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))

    data = json.loads(GrampsUploadMediaTool()._run(
        file_url="https://x.test/a.jpg", description="d"))

    assert data["success"] is False
    assert "no handle" in data["error"]
