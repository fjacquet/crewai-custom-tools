"""Offline tests for the batch-2a search & scraping provider tools."""

import json
import os

from crewai_custom_tools.tools.web.scraper import (
    BatchArticleScraperTool,
    FirecrawlTool,
    ScrapeNinjaTool,
)
from crewai_custom_tools.tools.web.search_providers import (
    BraveSearchTool,
    HybridSearchTool,
    SerpApiTool,
    TavilyTool,
)


def _data(result):
    payload = json.loads(result)
    assert payload["success"] is True, payload
    return payload["data"]


def _error(result):
    payload = json.loads(result)
    assert payload["success"] is False, payload
    return payload["error"]


# --- Brave -------------------------------------------------------------------


def test_brave_success(mocker):
    mocker.patch.dict(os.environ, {"BRAVE_API_KEY": "k"})
    resp = mocker.MagicMock()
    resp.json.return_value = {
        "web": {"results": [{"title": "T", "url": "http://x", "description": "d"}]}
    }
    mocker.patch("requests.get", return_value=resp)

    data = _data(BraveSearchTool()._run(query="ai"))
    assert data["results"][0]["url"] == "http://x"


def test_brave_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "BRAVE_API_KEY" in _error(BraveSearchTool()._run(query="ai"))


# --- Tavily ------------------------------------------------------------------


def test_tavily_success(mocker):
    mocker.patch.dict(os.environ, {"TAVILY_API_KEY": "k"})
    resp = mocker.MagicMock()
    resp.json.return_value = {
        "results": [{"title": "T", "url": "http://x", "content": "c"}],
        "answer": "an answer",
    }
    mocker.patch("requests.post", return_value=resp)

    data = _data(TavilyTool()._run(query="ai"))
    assert data["answer"] == "an answer"
    assert data["results"][0]["snippet"] == "c"


def test_tavily_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "TAVILY_API_KEY" in _error(TavilyTool()._run(query="ai"))


# --- SerpApi -----------------------------------------------------------------


def test_serpapi_success(mocker):
    mocker.patch.dict(os.environ, {"SERPAPI_API_KEY": "k"})
    resp = mocker.MagicMock()
    resp.json.return_value = {
        "organic_results": [{"title": "T", "link": "http://x", "snippet": "s"}]
    }
    mocker.patch("requests.get", return_value=resp)

    data = _data(SerpApiTool()._run(query="ai agents"))
    assert data["count"] == 1
    assert data["results"][0]["link"] == "http://x"


def test_serpapi_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "SERPAPI_API_KEY" in _error(SerpApiTool()._run(query="ai agents"))


def test_serpapi_short_query(mocker):
    mocker.patch.dict(os.environ, {"SERPAPI_API_KEY": "k"})
    assert "2 characters" in _error(SerpApiTool()._run(query="a"))


# --- Hybrid cascade ----------------------------------------------------------


def test_hybrid_falls_through_to_serper(mocker):
    """No Perplexity/Brave key -> cascade lands on a configured Serper."""
    mocker.patch.dict(os.environ, {"SERPER_API_KEY": "k"}, clear=True)
    resp = mocker.MagicMock()
    resp.json.return_value = {"organic": [{"title": "T", "snippet": "s", "link": "http://x"}]}
    mocker.patch("requests.post", return_value=resp)

    data = _data(HybridSearchTool()._run(query="ai"))
    assert data["provider"] == "serper"
    assert data["results"]["results"][0]["title"] == "T"


def test_hybrid_all_fail(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "All search providers failed" in _error(HybridSearchTool()._run(query="ai"))


# --- ScrapeNinja / Firecrawl / Batch ----------------------------------------


def test_scrapeninja_success(mocker):
    mocker.patch.dict(os.environ, {"RAPIDAPI_KEY": "k"})
    resp = mocker.MagicMock()
    resp.json.return_value = {"body": "<html><body><p>Ninja text.</p></body></html>"}
    mocker.patch("requests.post", return_value=resp)

    data = _data(ScrapeNinjaTool()._run(url="http://x"))
    assert data["provider"] == "scrapeninja"
    assert "Ninja text" in data["content"]


def test_scrapeninja_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "RAPIDAPI_KEY" in _error(ScrapeNinjaTool()._run(url="http://x"))


def test_firecrawl_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "FIRECRAWL_API_KEY" in _error(FirecrawlTool()._run(url="http://x"))


def test_batch_article_scraper(mocker):
    resp = mocker.MagicMock()
    resp.text = "<html><head><title>Page</title></head><body><p>Body text.</p></body></html>"
    mocker.patch("requests.get", return_value=resp)

    data = _data(BatchArticleScraperTool()._run(urls=["http://a", "http://b"]))
    assert data["count"] == 2
    assert "Body text" in data["articles"][0]["content"]
    assert data["articles"][1]["url"] == "http://b"
