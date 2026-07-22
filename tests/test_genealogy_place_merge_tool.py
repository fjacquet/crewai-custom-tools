import json

import httpx
import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig
from crewai_custom_tools.tools.genealogy.gramps.write_tools import GrampsMergePlacesTool

CONFIG = GrampsConfig(api_url="http://g.test/api", username="u", password="p")


@pytest.fixture(autouse=True)
def _no_global_dry_run(monkeypatch):
    monkeypatch.setenv("GENECREW_DRY_RUN", "false")


def _client(calls):
    def handler(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        if request.method == "POST" and "/merge/" in request.url.path:
            calls.append(request.url.path)
            return httpx.Response(200, json={})
        return httpx.Response(404)
    return GrampsClient(CONFIG, transport=httpx.MockTransport(handler))


def test_merge_dry_run_calls_nothing(mocker):
    calls = []
    mocker.patch.object(write_tools, "get_client", return_value=_client(calls))
    data = json.loads(GrampsMergePlacesTool()._run(keep_handle="A", merge_handle="B", dry_run=True))
    assert data["success"] is True and data["data"]["dry_run"] is True
    assert calls == []


def test_merge_posts_to_right_path(mocker):
    calls = []
    mocker.patch.object(write_tools, "get_client", return_value=_client(calls))
    GrampsMergePlacesTool()._run(keep_handle="A", merge_handle="B")
    assert calls == ["/api/places/A/merge/B"]
