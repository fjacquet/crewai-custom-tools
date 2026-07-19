"""Offline tests for the Gramps Web client (httpx.MockTransport, no network)."""

import json
import os
import time
from pathlib import Path

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


# -- on-disk token cache (opt-in via token_cache=) --------------------------


def test_token_cached_after_login(tmp_path):
    cache = tmp_path / "token.json"

    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        assert request.headers["Authorization"] == "Bearer tok-1"
        return httpx.Response(200, json=[{"name": "arbre"}])

    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/trees/") == [{"name": "arbre"}]

    assert cache.exists()
    cached = json.loads(cache.read_text())
    assert cached["token"] == "tok-1"
    assert "exp" in cached
    # credential on disk: must not be group/world readable
    assert (cache.stat().st_mode & 0o777) == 0o600


def test_cached_token_reused_without_relogin(tmp_path):
    cache = tmp_path / "token.json"
    cache.write_text(json.dumps({"token": "cached-tok", "exp": int(time.time()) + 3600}))

    def handler(request):
        if request.url.path == "/api/token/":
            raise AssertionError("must not re-login: a valid cached token exists")
        assert request.headers["Authorization"] == "Bearer cached-tok"
        return httpx.Response(200, json={"ok": True})

    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/people/") == {"ok": True}


def test_expired_cached_token_triggers_relogin(tmp_path):
    cache = tmp_path / "token.json"
    past_exp = int(time.time()) - 10
    cache.write_text(json.dumps({"token": "stale-tok", "exp": past_exp}))

    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/token/":
            return _token_response()
        assert request.headers["Authorization"] == "Bearer tok-1"
        return httpx.Response(200, json={"ok": True})

    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/people/") == {"ok": True}

    assert "/api/token/" in calls
    refreshed = json.loads(cache.read_text())
    assert refreshed["token"] == "tok-1"
    assert refreshed["exp"] > past_exp


def test_token_cache_created_atomically_with_0600(tmp_path, mocker):
    # Regression: the cache file must never exist at a world/group-readable
    # mode, even momentarily. Spy on Path.chmod to prove the implementation
    # creates the file pre-locked (os.open with mode=0o600) rather than
    # write_text() followed by a separate chmod() call.
    cache = tmp_path / "sub" / "token.json"

    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        return httpx.Response(200, json={"ok": True})

    chmod_spy = mocker.spy(Path, "chmod")
    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/people/") == {"ok": True}

    assert (cache.stat().st_mode & 0o777) == 0o600
    chmod_spy.assert_not_called()


def test_non_dict_cached_json_does_not_crash(tmp_path):
    cache = tmp_path / "token.json"
    cache.write_text("null")

    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        assert request.headers["Authorization"] == "Bearer tok-1"
        return httpx.Response(200, json={"ok": True})

    # Must not raise (previously: TypeError from "token" not in None).
    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/people/") == {"ok": True}


def test_non_dict_cached_json_number_does_not_crash(tmp_path):
    cache = tmp_path / "token.json"
    cache.write_text("42")

    def handler(request):
        if request.url.path == "/api/token/":
            return _token_response()
        return httpx.Response(200, json={"ok": True})

    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/people/") == {"ok": True}


def test_401_with_cache_invalidates_and_relogs_in(tmp_path):
    cache = tmp_path / "token.json"
    cache.write_text(json.dumps({"token": "stale-tok", "exp": int(time.time()) + 3600}))

    state = {"tokens": 0, "data_calls": 0}

    def handler(request):
        if request.url.path == "/api/token/":
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"tok-{state['tokens']}"})
        state["data_calls"] += 1
        if state["data_calls"] == 1:
            assert request.headers["Authorization"] == "Bearer stale-tok"
            return httpx.Response(401)
        assert request.headers["Authorization"] == "Bearer tok-1"
        return httpx.Response(200, json={"ok": True})

    client = GrampsClient(CONFIG, transport=_transport(handler), token_cache=cache)
    assert client.get_json("/people/") == {"ok": True}

    # Cached (stale) token used first with no eager relogin; exactly one
    # relogin happens after the 401, and the cache is rewritten with it.
    assert state["tokens"] == 1
    refreshed = json.loads(cache.read_text())
    assert refreshed["token"] == "tok-1"


# -- 429 login throttle retry -----------------------------------------------


def test_fetch_token_retries_once_on_429_then_succeeds():
    calls = {"tokens": 0}

    def handler(request):
        if request.url.path == "/api/token/":
            calls["tokens"] += 1
            if calls["tokens"] == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return _token_response()
        return httpx.Response(200, json={"ok": True})

    client = GrampsClient(CONFIG, transport=_transport(handler))
    assert client.get_json("/people/") == {"ok": True}
    assert calls["tokens"] == 2


def test_fetch_token_raises_after_exhausting_429_retries():
    calls = {"tokens": 0}

    def handler(request):
        if request.url.path == "/api/token/":
            calls["tokens"] += 1
            return httpx.Response(429, headers={"Retry-After": "0"})
        raise AssertionError("must not reach a data request without a token")

    client = GrampsClient(CONFIG, transport=_transport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.get_json("/people/")
    assert calls["tokens"] == 3
