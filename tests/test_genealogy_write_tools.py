"""Tests hors-ligne de GrampsUpdateNameTool (client mické)."""

import json

import httpx

from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import GrampsUpdateNameTool

CONFIG = GrampsConfig(api_url="http://g.test/api", username="u", password="p")

PERSON = {
    "handle": "h1", "gramps_id": "I0001", "gender": 1,
    "primary_name": {"first_name": "FREDERIC",
                     "surname_list": [{"surname": "JACQUET", "prefix": "", "primary": True}]},
}


def _mock(mocker, handler, captured=None):
    client = GrampsClient(CONFIG, transport=httpx.MockTransport(handler))
    mocker.patch(
        "crewai_custom_tools.tools.genealogy.gramps.write_tools.get_client",
        return_value=client,
    )


def test_update_name_writes_case_fix(mocker):
    puts = []

    def handler(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        if request.method == "GET":
            return httpx.Response(200, json=PERSON)
        if request.method == "PUT":
            puts.append(json.loads(request.content))
            return httpx.Response(200, json={})
        return httpx.Response(404)

    _mock(mocker, handler)
    payload = json.loads(GrampsUpdateNameTool()._run(handle="h1"))
    assert payload["success"] is True
    assert payload["data"]["dry_run"] is False
    by_field = {c["field"]: c for c in payload["data"]["changes"]}
    # prénom et nom sont des champs DISTINCTS, chacun étiqueté par son kind
    assert by_field["first_name"]["kind"] == "prénom"
    assert (by_field["first_name"]["old"], by_field["first_name"]["new"]) == ("FREDERIC", "Frederic")
    assert by_field["surname[0]"]["kind"] == "nom"
    assert (by_field["surname[0]"]["old"], by_field["surname[0]"]["new"]) == ("JACQUET", "Jacquet")
    # le PUT a bien envoyé la casse corrigée
    assert puts and puts[0]["primary_name"]["first_name"] == "Frederic"
    assert puts[0]["primary_name"]["surname_list"][0]["surname"] == "Jacquet"


def test_update_name_dry_run_does_not_put(mocker):
    def handler(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        if request.method == "GET":
            return httpx.Response(200, json=PERSON)
        raise AssertionError("aucun PUT attendu en dry_run")

    _mock(mocker, handler)
    payload = json.loads(GrampsUpdateNameTool()._run(handle="h1", dry_run=True))
    assert payload["success"] is True and payload["data"]["dry_run"] is True
    assert len(payload["data"]["changes"]) == 2


def test_update_name_no_change_when_already_mixed(mocker):
    already = {"handle": "h2", "gramps_id": "I0002",
               "primary_name": {"first_name": "Jean",
                                 "surname_list": [{"surname": "Dupont", "primary": True}]}}

    def handler(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        if request.method == "GET":
            return httpx.Response(200, json=already)
        raise AssertionError("aucun PUT attendu si rien à changer")

    _mock(mocker, handler)
    payload = json.loads(GrampsUpdateNameTool()._run(handle="h2"))
    assert payload["success"] is True and payload["data"]["changes"] == []
