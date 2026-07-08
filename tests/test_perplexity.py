"""Tests for PerplexitySearchTool."""

import json
import os

import pytest
import requests

from crewai_custom_tools.tools.web.perplexity import (
    PerplexitySearchInput,
    PerplexitySearchTool,
)

TEST_PERPLEXITY_API_KEY = "test_perplexity_key"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


@pytest.fixture
def mock_env_perplexity_key(mocker):
    """Mock environment with Perplexity API key."""
    mocker.patch.dict(
        os.environ, {"PERPLEXITY_API_KEY": TEST_PERPLEXITY_API_KEY}, clear=True
    )
    yield


@pytest.fixture
def mock_env_no_perplexity_key(mocker):
    """Mock environment without Perplexity API key."""
    mocker.patch.dict(os.environ, {}, clear=True)
    yield


def _mock_post(mocker, payload):
    mock_post = mocker.patch("requests.post")
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response
    return mock_post


def test_instantiation():
    """The tool exposes its name/description/schema."""
    tool = PerplexitySearchTool()
    assert tool.name == "perplexity_search"
    assert "AI-powered web search" in tool.description
    assert tool.args_schema == PerplexitySearchInput


def test_run_no_api_key(mock_env_no_perplexity_key):
    """_run returns an error envelope when the API key is missing (read at call time)."""
    result = json.loads(PerplexitySearchTool()._run(query="test query"))
    assert result["success"] is False
    assert "not configured" in result["error"]


def test_run_success(mock_env_perplexity_key, mocker):
    """A successful search returns the answer/citations under the envelope's data."""
    mock_post = _mock_post(
        mocker,
        {
            "choices": [{"message": {"content": "Test answer about Python."}}],
            "citations": ["https://python.org", "https://docs.python.org"],
        },
    )
    result = json.loads(PerplexitySearchTool()._run(query="What is Python?"))

    call_args = mock_post.call_args
    assert call_args[0][0] == PERPLEXITY_API_URL
    assert call_args[1]["json"]["messages"][0]["content"] == "What is Python?"
    assert result["success"] is True
    assert result["data"]["answer"] == "Test answer about Python."
    assert result["data"]["citations"] == ["https://python.org", "https://docs.python.org"]
    assert result["data"]["source"] == "perplexity"


def test_focus_academic_sets_search_mode(mock_env_perplexity_key, mocker):
    """focus='academic' adds search_mode to the request payload."""
    mock_post = _mock_post(
        mocker, {"choices": [{"message": {"content": "scholarly"}}]}
    )
    PerplexitySearchTool()._run(query="q", focus="academic", recency="day")
    body = mock_post.call_args[1]["json"]
    assert body["search_mode"] == "academic"
    assert body["search_recency_filter"] == "day"


def test_focus_reddit_sets_domain_filter(mock_env_perplexity_key, mocker):
    """focus='reddit' restricts the domain filter to reddit.com."""
    mock_post = _mock_post(mocker, {"choices": [{"message": {"content": "r/"}}]})
    PerplexitySearchTool()._run(query="q", focus="reddit")
    assert mock_post.call_args[1]["json"]["search_domain_filter"] == ["reddit.com"]


def test_focus_internet_adds_no_extra_params(mock_env_perplexity_key, mocker):
    """The default focus sends no search_mode/domain filter."""
    mock_post = _mock_post(mocker, {"choices": [{"message": {"content": "x"}}]})
    PerplexitySearchTool()._run(query="q", focus="internet")
    body = mock_post.call_args[1]["json"]
    assert "search_mode" not in body
    assert "search_domain_filter" not in body


def test_run_missing_content_returns_error(mock_env_perplexity_key, mocker):
    """A 200 with no answer content returns an error envelope, not a crash."""
    _mock_post(mocker, {"choices": []})
    result = json.loads(PerplexitySearchTool()._run(query="q"))
    assert result["success"] is False
    assert "no answer" in result["error"].lower()


def test_run_api_error(mock_env_perplexity_key, mocker):
    """A network error is caught by the decorator and returned as an error envelope."""
    mocker.patch(
        "requests.post",
        side_effect=requests.exceptions.RequestException("Connection failed"),
    )
    result = json.loads(PerplexitySearchTool()._run(query="test query"))
    assert result["success"] is False
    assert "Connection failed" in result["error"]


def test_input_schema_defaults():
    """PerplexitySearchInput default values."""
    input_data = PerplexitySearchInput(query="test")
    assert input_data.query == "test"
    assert input_data.focus == "internet"
    assert input_data.recency == "week"
