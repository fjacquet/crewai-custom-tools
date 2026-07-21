import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import (
    GrampsCreateEventTool, GrampsCreatePersonTool,
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


# --- CreateEvent ---

# Personne avec une naissance déjà posée mais AUCUN décès (death_ref_index=-1) :
# c'est le cas d'un `net` dont le relevé apporte le décès manquant.
_PERSON_SANS_DECES = {
    "_class": "Person", "handle": "H", "gramps_id": "I0001", "gender": 0,
    "primary_name": {"_class": "Name", "first_name": "Rose",
                     "surname_list": [{"_class": "Surname", "surname": "Jacquet"}]},
    "event_ref_list": [{"_class": "EventRef", "ref": "E_BIRTH", "role": "Primary"}],
    "birth_ref_index": 0, "death_ref_index": -1,
}


def test_create_event_dry_run_posts_and_puts_nothing(mocker):
    calls = []

    def h(request):
        calls.append(request.method + " " + request.url.path)
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreateEventTool()._run(
        person_handle="H", event_type="Death", dateval=[10, 12, 1894], dry_run=True))
    assert data["success"] is True
    assert data["data"]["handle"] == "DRYRUN:event"
    assert data["data"]["created"] is False and data["data"]["attached"] is False
    assert not any(c.startswith("POST") for c in calls)
    assert not any(c.startswith("PUT") for c in calls)


def test_create_event_posts_event_then_attaches_and_sets_death_index(mocker):
    posts, puts = [], []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/events/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json=[{"type": "add", "_class": "Event", "handle": "E_NEW"}])
        if request.method == "GET" and request.url.path == "/api/people/H":
            return httpx.Response(200, json=dict(_PERSON_SANS_DECES))
        if request.method == "PUT" and request.url.path == "/api/people/H":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreateEventTool()._run(
        person_handle="H", event_type="Death", dateval=[10, 12, 1894],
        place_handle="P_SMA", citation_handle="C1"))

    assert data["data"]["handle"] == "E_NEW"
    assert data["data"]["created"] is True and data["data"]["attached"] is True
    # Payload de l'événement : type, date exacte, lieu (handle), citation.
    ev = posts[0]
    assert ev["type"] == "Death"
    assert ev["date"] == {"_class": "Date", "modifier": 0, "quality": 0,
                          "dateval": [10, 12, 1894, False]}
    assert ev["place"] == "P_SMA"
    assert ev["citation_list"] == ["C1"]
    # Rattachement : EventRef ajouté en fin de liste, death_ref_index pointe dessus.
    put = puts[0]
    assert put["event_ref_list"] == [
        {"_class": "EventRef", "ref": "E_BIRTH", "role": "Primary"},
        {"_class": "EventRef", "ref": "E_NEW", "role": "Primary"},
    ]
    assert put["death_ref_index"] == 1
    assert put["birth_ref_index"] == 0            # inchangé
    # Append-only sur le reste de la personne.
    for k in ("gender", "gramps_id", "primary_name", "_class"):
        assert put[k] == _PERSON_SANS_DECES[k]


def test_create_event_without_place_or_citation_omits_them(mocker):
    posts = []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/events/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json=[{"handle": "E_NEW"}])
        if request.method == "GET" and request.url.path == "/api/people/H":
            return httpx.Response(200, json=dict(_PERSON_SANS_DECES))
        if request.method == "PUT" and request.url.path == "/api/people/H":
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    json.loads(GrampsCreateEventTool()._run(
        person_handle="H", event_type="Death", dateval=[10, 12, 1894]))
    ev = posts[0]
    assert "place" not in ev              # pas de lieu : pas de clé place
    assert "citation_list" not in ev      # pas de citation : pas de clé


def test_create_event_dryrun_place_handle_is_not_written(mocker):
    # Un place_handle synthétique 'DRYRUN:...' (lieu simulé en amont) ne doit jamais
    # entrer dans le payload d'un événement écrit pour de vrai.
    posts = []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/events/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json=[{"handle": "E_NEW"}])
        if request.method == "GET" and request.url.path == "/api/people/H":
            return httpx.Response(200, json=dict(_PERSON_SANS_DECES))
        if request.method == "PUT" and request.url.path == "/api/people/H":
            return httpx.Response(200, json={})
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    json.loads(GrampsCreateEventTool()._run(
        person_handle="H", event_type="Death", dateval=[10, 12, 1894],
        place_handle="DRYRUN:Saint-Martin"))
    assert "place" not in posts[0]


# --- CreatePerson ---

def test_create_person_dry_run_posts_nothing(mocker):
    calls = []

    def h(request):
        calls.append(request.method + " " + request.url.path)
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreatePersonTool()._run(
        first_name="Rose", surname="Jacquet", gender=0, dry_run=True))
    assert data["data"]["handle"] == "DRYRUN:person"
    assert data["data"]["created"] is False
    assert not any(c.startswith("POST") for c in calls)


def test_create_person_posts_name_and_gender(mocker):
    posts = []

    def h(request):
        if request.method == "POST" and request.url.path == "/api/people/":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json=[{"type": "add", "_class": "Person", "handle": "H_NEW"}])
        return httpx.Response(404)
    mocker.patch.object(write_tools, "get_client", return_value=_client(h))
    data = json.loads(GrampsCreatePersonTool()._run(
        first_name="Rose", surname="Jacquet", gender=0))
    assert data["data"]["handle"] == "H_NEW" and data["data"]["created"] is True
    p = posts[0]
    assert p["_class"] == "Person" and p["gender"] == 0
    assert p["primary_name"]["first_name"] == "Rose"
    assert p["primary_name"]["surname_list"] == [{"_class": "Surname", "surname": "Jacquet"}]
