"""Tests for PerplexitySearchTool."""

import pytest

from crewai_custom_tools import PerplexitySearchTool
from crewai_custom_tools.core.results import ToolResultError, parse_tool_result


@pytest.fixture()
def pplx_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")


def _mock_response(mocker, payload):
    response = mocker.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_construction_fails_fast_without_key(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    with pytest.raises(ValueError, match="PERPLEXITY_API_KEY or PPLX_API_KEY"):
        PerplexitySearchTool()


def test_legacy_pplx_key_still_works(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.setenv("PPLX_API_KEY", "legacy-key")
    assert PerplexitySearchTool() is not None


def test_run_returns_answer_envelope(pplx_key, mocker):
    post = mocker.patch(
        "crewai_custom_tools.tools.web.perplexity.requests.post",
        return_value=_mock_response(
            mocker,
            {
                "choices": [{"message": {"content": "The answer."}}],
                "citations": ["https://example.com"],
            },
        ),
    )
    data = parse_tool_result(PerplexitySearchTool()._run(query="test question"))
    assert data == {"answer": "The answer.", "citations": ["https://example.com"], "source": "perplexity"}
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "sonar-pro"
    assert payload["top_k"] == 5
    assert "search_recency_filter" not in payload


def test_recency_maps_to_search_recency_filter(pplx_key, mocker):
    post = mocker.patch(
        "crewai_custom_tools.tools.web.perplexity.requests.post",
        return_value=_mock_response(
            mocker, {"choices": [{"message": {"content": "x"}}], "citations": []}
        ),
    )
    PerplexitySearchTool()._run(query="q", search_recency="week", search_domain_filter=["reddit.com"])
    payload = post.call_args.kwargs["json"]
    assert payload["search_recency_filter"] == "week"
    assert payload["search_domain_filter"] == ["reddit.com"]


def test_missing_answer_yields_error_envelope(pplx_key, mocker):
    mocker.patch(
        "crewai_custom_tools.tools.web.perplexity.requests.post",
        return_value=_mock_response(mocker, {"choices": []}),
    )
    with pytest.raises(ToolResultError, match="no answer"):
        parse_tool_result(PerplexitySearchTool()._run(query="q"))
