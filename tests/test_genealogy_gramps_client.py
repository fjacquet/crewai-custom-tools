"""Offline tests for the Gramps Web client (httpx.MockTransport, no network)."""

import json
import os

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps.client import (
    GrampsClient,
    GrampsConfig,
    GrampsConfigError,
)

CONFIG = GrampsConfig(api_url="http://gramps.test/api", username="u", password="p")


def _transport(handler):
    return httpx.MockTransport(handler)


def _token_response():
    return httpx.Response(200, json={"access_token": "tok-1"})


def test_from_env_reads_variables(mocker):
    mocker.patch.dict(
        os.environ,
        {"GRAMPS_API_URL": "http://h/api/", "GRAMPS_USERNAME": "u", "GRAMPS_PASSWORD": "p"},
    )
    cfg = GrampsConfig.from_env()
    assert cfg.api_url == "http://h/api"  # trailing slash stripped
    assert cfg.username == "u"


def test_from_env_missing_variable_raises(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    with pytest.raises(GrampsConfigError):
        GrampsConfig.from_env()


def test_get_json_fetches_token_then_data():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/token/":
            assert json.loads(request.content) == {"username": "u", "password": "p"}
            return _token_response()
        assert request.headers["Authorization"] == "Bearer tok-1"
        return httpx.Response(200, json=[{"name": "arbre"}])

    client = GrampsClient(CONFIG, transport=_transport(handler))
    assert client.get_json("/trees/") == [{"name": "arbre"}]
    assert calls[0] == ("POST", "/api/token/")


def test_request_refreshes_token_once_on_401():
    state = {"tokens": 0, "data_calls": 0}

    def handler(request):
        if request.url.path == "/api/token/":
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"tok-{state['tokens']}"})
        state["data_calls"] += 1
        if state["data_calls"] == 1:
            return httpx.Response(401)
        assert request.headers["Authorization"] == "Bearer tok-2"
        return httpx.Response(200, json={"ok": True})

    client = GrampsClient(CONFIG, transport=_transport(handler))
    assert client.get_json("/people/") == {"ok": True}
    assert state["tokens"] == 2  # initial + refresh


def test_count_objects_uses_total_count_header():
    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        assert request.url.params["pagesize"] == "1"
        return httpx.Response(200, json=[{}], headers={"X-Total-Count": "1234"})

    client = GrampsClient(CONFIG, transport=_transport(handler))
    assert client.count_objects("people") == 1234


def test_count_objects_missing_header_raises():
    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        return httpx.Response(200, json=[{}])

    client = GrampsClient(CONFIG, transport=_transport(handler))
    with pytest.raises(RuntimeError, match="X-Total-Count"):
        client.count_objects("people")


def test_find_by_gramps_id_returns_single_object():
    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        assert request.url.params["gramps_id"] == "I0042"
        return httpx.Response(200, json=[{"gramps_id": "I0042", "handle": "abc"}])

    client = GrampsClient(CONFIG, transport=_transport(handler))
    assert client.find_by_gramps_id("people", "I0042")["handle"] == "abc"


def test_http_error_propagates_as_status_error():
    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        return httpx.Response(500)

    client = GrampsClient(CONFIG, transport=_transport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.get_json("/people/")
