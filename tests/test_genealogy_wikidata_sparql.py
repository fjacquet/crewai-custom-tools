# tests/test_genealogy_wikidata_sparql.py
import pytest
import requests

from crewai_custom_tools.tools.web import wikidata


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_sparql_rows_flattens_bindings(monkeypatch):
    payload = {
        "head": {"vars": ["item", "dissolved"]},
        "results": {"bindings": [
            {"item": {"value": "http://www.wikidata.org/entity/Q25398054"},
             "dissolved": {"value": "1972-12-31T00:00:00Z"}},
        ]},
    }
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen["url"] = url
        seen["query"] = params["query"]
        seen["format"] = params["format"]
        return _FakeResponse(payload)

    monkeypatch.setattr(wikidata.requests, "get", fake_get)
    query = "SELECT ?item WHERE { ?item wdt:P374 '55451' }"
    rows = wikidata.sparql_rows(query)
    assert rows == [{"item": "http://www.wikidata.org/entity/Q25398054",
                     "dissolved": "1972-12-31T00:00:00Z"}]
    assert seen["url"] == wikidata.SPARQL_ENDPOINT
    assert seen["format"] == "json"
    assert seen["query"] == query


def test_sparql_rows_empty_results(monkeypatch):
    monkeypatch.setattr(wikidata.requests, "get",
                        lambda *a, **k: _FakeResponse({"results": {"bindings": []}}))
    assert wikidata.sparql_rows("SELECT ?x WHERE { ?x wdt:P374 '00000' }") == []


def test_sparql_rows_raises_on_http_error(monkeypatch):
    class _FailingResponse(_FakeResponse):
        def raise_for_status(self):
            raise requests.HTTPError("500")

    monkeypatch.setattr(wikidata.requests, "get",
                        lambda *a, **k: _FailingResponse({}))
    with pytest.raises(requests.HTTPError):
        wikidata.sparql_rows("SELECT ?x WHERE { ?x wdt:P374 '00000' }")
