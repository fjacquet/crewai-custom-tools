"""Offline tests for the Gramps read tools (client mocked, envelope asserted)."""

import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.read_tools import (
    GrampsGetObjectTool,
    GrampsListPeopleTool,
    GrampsSearchTool,
    GrampsTimelineTool,
    GrampsTreeStatsTool,
)

CONFIG = GrampsConfig(api_url="http://gramps.test/api", username="u", password="p")


def _client(handler):
    return GrampsClient(CONFIG, transport=httpx.MockTransport(handler))


def _mock_client(mocker, handler):
    client = _client(handler)
    mocker.patch(
        "crewai_custom_tools.tools.genealogy.gramps.read_tools.get_client",
        return_value=client,
    )


def _token_or(request, respond):
    if request.url.path == "/api/token/":
        return httpx.Response(200, json={"access_token": "tok"})
    return respond(request)


def test_search_tool_success(mocker):
    def handler(request):
        return _token_or(
            request,
            lambda r: httpx.Response(
                200, json=[{"object_type": "person", "object": {"gramps_id": "I0001"}}]
            ),
        )

    _mock_client(mocker, handler)
    payload = json.loads(GrampsSearchTool()._run(query="Dupont"))
    assert payload["success"] is True
    assert payload["data"][0]["object"]["gramps_id"] == "I0001"


def test_search_tool_empty_is_success(mocker):
    def handler(request):
        return _token_or(request, lambda r: httpx.Response(200, json=[]))

    _mock_client(mocker, handler)
    payload = json.loads(GrampsSearchTool()._run(query="Zzz"))
    assert payload["success"] is True
    assert payload["data"] == []


def test_get_object_tool_by_gramps_id(mocker):
    def handler(request):
        def respond(r):
            assert r.url.params["gramps_id"] == "I0042"
            return httpx.Response(200, json=[{"handle": "abc", "gramps_id": "I0042"}])

        return _token_or(request, respond)

    _mock_client(mocker, handler)
    payload = json.loads(
        GrampsGetObjectTool()._run(object_type="people", gramps_id="I0042")
    )
    assert payload["success"] is True
    assert payload["data"]["handle"] == "abc"


def test_get_object_tool_requires_identifier(mocker):
    _mock_client(mocker, lambda r: httpx.Response(500))
    payload = json.loads(GrampsGetObjectTool()._run(object_type="people"))
    assert payload["success"] is False


def test_tree_stats_tool_counts_all_types(mocker):
    def handler(request):
        def respond(r):
            if r.url.path == "/api/trees/":
                return httpx.Response(200, json=[{"name": "Famille"}])
            return httpx.Response(200, json=[{}], headers={"X-Total-Count": "7"})

        return _token_or(request, respond)

    _mock_client(mocker, handler)
    payload = json.loads(GrampsTreeStatsTool()._run())
    assert payload["success"] is True
    assert payload["data"]["tree_name"] == "Famille"
    assert payload["data"]["counts"]["people"] == 7


def test_list_people_tool_error_path(mocker):
    def handler(request):
        return _token_or(request, lambda r: httpx.Response(500))

    _mock_client(mocker, handler)
    payload = json.loads(GrampsListPeopleTool()._run())
    assert payload["success"] is False


def test_timeline_tool_success(mocker):
    def handler(request):
        def respond(r):
            assert r.url.path == "/api/people/abc/timeline"
            return httpx.Response(200, json=[{"label": "Birth"}])

        return _token_or(request, respond)

    _mock_client(mocker, handler)
    payload = json.loads(GrampsTimelineTool()._run(handle="abc"))
    assert payload["success"] is True
    assert payload["data"][0]["label"] == "Birth"
