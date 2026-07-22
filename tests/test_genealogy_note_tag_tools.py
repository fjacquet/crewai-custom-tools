import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import (
    GrampsAttachTool,
    GrampsCreateNoteTool,
    GrampsEnsureTagTool,
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


# --- CreateNote ---

def test_create_note_dry_run_posts_nothing(mocker):
    calls = []

    def h(request):
        calls.append(request.method + " " + request.url.path)
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreateNoteTool()._run(text="[genecrew:audit] souci", dry_run=True))
    assert data["success"] is True
    assert data["data"]["handle"] == "DRYRUN:note" and data["data"]["created"] is False
    assert not any(c.startswith("POST") for c in calls)      # aucun POST


def test_create_note_posts_styledtext_and_returns_handle(mocker):
    posts = []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/notes/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json=[{"type": "add", "_class": "Note", "handle": "N1"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreateNoteTool()._run(text="bonjour", note_type="Research"))
    assert data["data"]["handle"] == "N1" and data["data"]["created"] is True
    assert posts[0]["type"] == "Research"
    assert posts[0]["text"] == {"_class": "StyledText", "string": "bonjour", "tags": []}


# --- EnsureTag (idempotent) ---

def test_ensure_tag_returns_existing_without_creating(mocker):
    posts = []

    def h(request):
        if request.method == "GET" and request.url.path == "/api/tags/":
            return httpx.Response(200, json=[{"name": "ia-anomalie", "handle": "TAG_EXIST"}])
        if request.method == "POST":
            posts.append(request.url.path)
            return httpx.Response(201, json=[{"handle": "SHOULD_NOT"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsEnsureTagTool()._run(name="ia-anomalie"))
    assert data["data"]["handle"] == "TAG_EXIST" and data["data"]["created"] is False
    assert posts == []                                       # idempotent : rien créé


def test_ensure_tag_creates_when_absent(mocker):
    def h(request):
        if request.method == "GET" and request.url.path == "/api/tags/":
            return httpx.Response(200, json=[{"name": "autre", "handle": "X"}])
        if request.method == "POST" and request.url.path == "/api/tags/":
            body = json.loads(request.content)
            assert body["name"] == "ia-a-verifier"
            return httpx.Response(201, json=[{"type": "add", "_class": "Tag", "handle": "TAG_NEW"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsEnsureTagTool()._run(name="ia-a-verifier"))
    assert data["data"]["handle"] == "TAG_NEW" and data["data"]["created"] is True


# --- Attach (append-only strict) ---

_PERSON = {"_class": "Person", "handle": "H", "gramps_id": "I0001", "gender": 1,
           "note_list": ["N_OLD"], "tag_list": [], "primary_name": {"first_name": "Jean"}}


def test_attach_appends_only_note_and_tag_lists(mocker):
    puts = []

    def h(request):
        if request.method == "GET" and request.url.path == "/api/people/H":
            return httpx.Response(200, json=_PERSON)
        if request.method == "PUT" and request.url.path == "/api/people/H":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsAttachTool()._run(handle="H", note_handle="N1", tag_handle="T1"))
    assert data["data"]["changed"] is True
    put = puts[0]
    assert put["note_list"] == ["N_OLD", "N1"]               # append, pas d'écrasement
    assert put["tag_list"] == ["T1"]
    # invariant append-only : tout le reste est identique à l'objet lu
    for k in ("gender", "gramps_id", "primary_name", "_class"):
        assert put[k] == _PERSON[k]


def test_attach_dedups_and_dry_run_writes_nothing(mocker):
    puts = []

    def h(request):
        if request.method == "GET" and request.url.path == "/api/people/H":
            return httpx.Response(200, json=_PERSON)
        if request.method == "PUT":
            puts.append(request.url.path)
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    # note déjà présente -> aucun changement ; dry-run -> aucune écriture
    already = json.loads(GrampsAttachTool()._run(handle="H", note_handle="N_OLD"))
    assert already["data"]["changed"] is False
    dry = json.loads(GrampsAttachTool()._run(handle="H", tag_handle="T1", dry_run=True))
    assert dry["data"]["added"]["tag"] == "T1" and dry["data"]["dry_run"] is True
    assert puts == []                                        # rien écrit
