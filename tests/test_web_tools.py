"""Mock-based unit tests for unified web and search tools."""

import json
import os

import requests

from crewai_custom_tools.tools.web.fact_checking import GoogleFactCheckTool
from crewai_custom_tools.tools.web.rss import OpmlParserTool, RssFeedParserTool
from crewai_custom_tools.tools.web.scraper import UnifiedScraperTool
from crewai_custom_tools.tools.web.serper import SerperSearchTool
from crewai_custom_tools.tools.web.wikipedia import (
    ArticleAction,
    WikipediaArticleTool,
    WikipediaSearchTool,
)


def _data(result_str):
    """Assert an envelope success and return its data payload."""
    payload = json.loads(result_str)
    assert payload["success"] is True, payload
    return payload["data"]


# 1. Serper -------------------------------------------------------------------


def test_serper_search_success(mocker):
    mocker.patch.dict(os.environ, {"SERPER_API_KEY": "test_serper_key"})
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {"title": "Test Result 1", "snippet": "Snippet 1", "link": "http://link1.com"},
            {"title": "Test Result 2", "snippet": "Snippet 2", "link": "http://link2.com"},
        ]
    }
    mocker.patch("requests.post", return_value=mock_response)

    data = _data(SerperSearchTool()._run(query="AI Agents"))
    assert data["query"] == "AI Agents"
    assert data["results"][0]["title"] == "Test Result 1"
    assert data["results"][1]["link"] == "http://link2.com"


def test_serper_search_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    result = json.loads(SerperSearchTool()._run(query="AI Agents"))
    assert result["success"] is False
    assert "SERPER_API_KEY" in result["error"]


def test_serper_ignores_serply_key(mocker):
    """SERPLY_API_KEY is a different vendor and must not be accepted."""
    mocker.patch.dict(os.environ, {"SERPLY_API_KEY": "wrong"}, clear=True)
    result = json.loads(SerperSearchTool()._run(query="q"))
    assert result["success"] is False


# 2. Unified Scraper ----------------------------------------------------------


def test_unified_scraper_standard_success(mocker):
    mock_response = mocker.MagicMock()
    mock_response.text = (
        "<html><head><title>My Test Page</title></head>"
        "<body><p>Hello world from scraper.</p></body></html>"
    )
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(UnifiedScraperTool()._run(url="http://example.com", provider="standard"))
    assert data["provider"] == "standard"
    assert data["title"] == "My Test Page"
    assert "Hello world" in data["content"]


def test_unified_scraper_scrapeninja_has_uniform_title_key(mocker):
    """Fallback providers still expose a `title` key (uniform schema)."""
    mocker.patch.dict(os.environ, {"RAPIDAPI_KEY": "test_rapidapi_key"})
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "body": "<html><body><p>ScrapeNinja content.</p></body></html>"
    }
    mocker.patch("requests.post", return_value=mock_response)

    data = _data(UnifiedScraperTool()._run(url="http://example.com", provider="scrapeninja"))
    assert data["provider"] == "scrapeninja"
    assert "title" in data  # present even though None
    assert "ScrapeNinja content" in data["content"]


def test_unified_scraper_auto_escalation(mocker):
    mocker.patch.dict(os.environ, {"RAPIDAPI_KEY": "test_rapidapi_key"})
    mocker.patch(
        "requests.get",
        side_effect=requests.exceptions.RequestException("Blocked by Cloudflare"),
    )
    mock_ninja_response = mocker.MagicMock()
    mock_ninja_response.json.return_value = {
        "body": "<html><body><p>Escalated Ninja content.</p></body></html>"
    }
    mocker.patch("requests.post", return_value=mock_ninja_response)

    data = _data(UnifiedScraperTool()._run(url="http://example.com"))
    assert data["provider"] == "scrapeninja"
    assert "Escalated Ninja content" in data["content"]


# 3. Wikipedia ----------------------------------------------------------------


def test_wikipedia_search(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "query": {"search": [{"title": "Artificial intelligence"}, {"title": "Intelligent agent"}]}
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(WikipediaSearchTool()._run(query="AI"))
    assert data == ["Artificial intelligence", "Intelligent agent"]


def test_wikipedia_article_summary(mocker):
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"extract": "Python is a high-level programming language."}
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(
        WikipediaArticleTool()._run(
            title="Python (programming language)", action=ArticleAction.GET_SUMMARY
        )
    )
    assert "high-level" in data["summary"]


def test_wikipedia_get_sections_uses_parse_api(mocker):
    """get_sections returns structured section titles from the parse API."""
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "parse": {"sections": [{"line": "History"}, {"line": "Syntax"}, {"line": "See also"}]}
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(
        WikipediaArticleTool()._run(title="Python", action=ArticleAction.GET_SECTIONS)
    )
    assert data["sections"] == ["History", "Syntax", "See also"]


# 4. RSS / OPML ---------------------------------------------------------------


def test_rss_feed_parser(mocker):
    mock_feed = mocker.MagicMock()
    mock_feed.bozo = False
    mock_feed.status = 200
    mock_entry = mocker.MagicMock()
    mock_entry.get.side_effect = lambda key, default=None: {
        "title": "Recent AI News",
        "link": "http://rss.com/ai",
        "published": "Sun, 05 Jul 2026 12:00:00 GMT",
    }.get(key, default)
    mock_entry.published_parsed = (2026, 7, 5, 12, 0, 0, 6, 186, 0)
    mock_entry.summary = "A summary of recent news."
    mock_feed.entries = [mock_entry]
    mocker.patch("feedparser.parse", return_value=mock_feed)

    # Use a wide window so the fixed date passes regardless of "today".
    data = _data(RssFeedParserTool()._run(feed_url="http://rss.com/feed", days=100000))
    assert data[0]["title"] == "Recent AI News"
    assert data[0]["published"] == "Sun, 05 Jul 2026 12:00:00 GMT"


def test_opml_parser_success(tmp_path):
    opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head><title>My Feeds</title></head>
    <body>
        <outline text="Tech Feeds">
            <outline text="AI Feed" type="rss" xmlUrl="https://rss.com/ai" htmlUrl="https://rss.com"/>
            <outline text="Python Feed" type="rss" xmlUrl="https://rss.com/python" htmlUrl="https://rss.com"/>
        </outline>
    </body>
</opml>"""
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(opml_content)

    data = _data(OpmlParserTool()._run(opml_file_path=str(opml_file)))
    assert isinstance(data, list)
    assert "https://rss.com/ai" in data
    assert "https://rss.com/python" in data


def test_opml_parser_file_not_found():
    result = json.loads(OpmlParserTool()._run(opml_file_path="/nonexistent/file.opml"))
    assert result["success"] is False
    assert "not found" in result["error"]


# 5. Google Fact Check --------------------------------------------------------


def test_google_fact_check_success(mocker):
    mocker.patch.dict(os.environ, {"GOOGLE_API_KEY": "test_google_key"})
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "claims": [
            {
                "text": "The moon is made of green cheese",
                "claimReview": [
                    {"publisher": {"name": "FactCheck.org"}, "textualRating": "False"}
                ],
            }
        ]
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(GoogleFactCheckTool()._run(query="moon green cheese"))
    assert data["claims"][0]["text"] == "The moon is made of green cheese"
    assert data["claims"][0]["claimReview"][0]["publisher"]["name"] == "FactCheck.org"
