"""Mock-based unit tests for unified web and search tools."""

import json
import os
import pytest
import requests
from crew_custom_tools.tools.web.serper import SerperSearchTool
from crew_custom_tools.tools.web.scraper import UnifiedScraperTool
from crew_custom_tools.tools.web.wikipedia import WikipediaSearchTool, WikipediaArticleTool, ArticleAction
from crew_custom_tools.tools.web.rss import RssFeedParserTool, OpmlParserTool
from crew_custom_tools.tools.web.fact_checking import GoogleFactCheckTool


# ==============================================================================
# 1. Serper Tool Tests
# ==============================================================================

def test_serper_search_success(mocker):
    """Test successful Serper search and formatting."""
    mocker.patch.dict(os.environ, {"SERPER_API_KEY": "test_serper_key"})
    
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "organic": [
            {"title": "Test Result 1", "snippet": "Snippet 1", "link": "http://link1.com"},
            {"title": "Test Result 2", "snippet": "Snippet 2", "link": "http://link2.com"}
        ]
    }
    mocker.patch("requests.post", return_value=mock_response)

    tool = SerperSearchTool()
    result = tool._run(query="AI Agents")
    
    assert "Search results for: AI Agents" in result
    assert "Test Result 1" in result
    assert "Snippet 2" in result
    assert "http://link1.com" in result


def test_serper_search_missing_key(mocker):
    """Test Serper search returns error when no API key is set."""
    mocker.patch.dict(os.environ, {}, clear=True)
    tool = SerperSearchTool()
    result = tool._run(query="AI Agents")
    assert "SERPER_API_KEY environment variable not set" in result


# ==============================================================================
# 2. Unified Scraper Tests
# ==============================================================================

def test_unified_scraper_standard_success(mocker):
    """Test standard BeautifulSoup scraper handles basic HTML."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><head><title>My Test Page</title></head><body><p>Hello world from scraper.</p></body></html>"
    mocker.patch("requests.get", return_value=mock_response)

    tool = UnifiedScraperTool()
    result_str = tool._run(url="http://example.com", provider="standard")
    result = json.loads(result_str)
    
    assert result["success"] is True
    assert result["provider"] == "standard"
    assert result["title"] == "My Test Page"
    assert "Hello world" in result["content"]


def test_unified_scraper_scrapeninja_success(mocker):
    """Test ScrapeNinja proxy API is invoked cleanly when forced."""
    mocker.patch.dict(os.environ, {"RAPIDAPI_KEY": "test_rapidapi_key"})
    
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "body": "<html><body><p>ScrapeNinja content.</p></body></html>"
    }
    mocker.patch("requests.post", return_value=mock_response)

    tool = UnifiedScraperTool()
    result_str = tool._run(url="http://example.com", provider="scrapeninja")
    result = json.loads(result_str)
    
    assert result["success"] is True
    assert result["provider"] == "scrapeninja"
    assert "ScrapeNinja content" in result["content"]


def test_unified_scraper_auto_escalation(mocker):
    """Test that standard scraping failures automatically trigger ScrapeNinja fallback escalation."""
    mocker.patch.dict(os.environ, {"RAPIDAPI_KEY": "test_rapidapi_key"})
    
    # 1. First standard request fails
    mocker.patch("requests.get", side_effect=requests.exceptions.RequestException("Blocked by Cloudflare"))
    
    # 2. Mock ScrapeNinja escalation call success
    mock_ninja_response = mocker.MagicMock()
    mock_ninja_response.status_code = 200
    mock_ninja_response.json.return_value = {
        "body": "<html><body><p>Escalated Ninja content.</p></body></html>"
    }
    mocker.patch("requests.post", return_value=mock_ninja_response)

    tool = UnifiedScraperTool()
    result_str = tool._run(url="http://example.com") # No provider forced
    result = json.loads(result_str)
    
    assert result["success"] is True
    assert result["provider"] == "scrapeninja"
    assert "Escalated Ninja content" in result["content"]


# ==============================================================================
# 3. Wikipedia Tool Tests
# ==============================================================================

def test_wikipedia_search(mocker):
    """Test searching titles on Wikipedia."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "query": {
            "search": [
                {"title": "Artificial intelligence"},
                {"title": "Intelligent agent"}
            ]
        }
    }
    mocker.patch("requests.get", return_value=mock_response)

    tool = WikipediaSearchTool()
    result_str = tool._run(query="AI")
    results = json.loads(result_str)
    
    assert len(results) == 2
    assert results[0] == "Artificial intelligence"


def test_wikipedia_article_summary(mocker):
    """Test fetching a summary extract of a Wikipedia article."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "extract": "Python is a high-level programming language."
    }
    mocker.patch("requests.get", return_value=mock_response)

    tool = WikipediaArticleTool()
    result = tool._run(title="Python (programming language)", action=ArticleAction.GET_SUMMARY)
    assert "Python is a high-level" in result


# ==============================================================================
# 4. RSS Feed Tool Tests
# ==============================================================================

def test_rss_feed_parser(mocker):
    """Test RSS Feed parsing fetches and filters posts correctly."""
    mock_feed = mocker.MagicMock()
    mock_feed.bozo = False
    mock_feed.status = 200
    
    # Mocking feed entries with 9-tuple structures for published_parsed (year, month, day, hr, min, sec...)
    mock_entry_1 = mocker.MagicMock()
    mock_entry_1.get.side_effect = lambda key, default=None: {
        "title": "Recent AI News",
        "link": "http://rss.com/ai",
        "published": "Sun, 05 Jul 2026 12:00:00 GMT"
    }.get(key, default)
    mock_entry_1.published_parsed = (2026, 7, 5, 12, 0, 0, 6, 186, 0)
    mock_entry_1.summary = "A summary of recent news."

    mock_feed.entries = [mock_entry_1]
    mocker.patch("feedparser.parse", return_value=mock_feed)

    tool = RssFeedParserTool()
    result_str = tool._run(feed_url="http://rss.com/feed", days=7)
    results = json.loads(result_str)
    
    assert len(results) == 1
    assert results[0]["title"] == "Recent AI News"
    assert results[0]["published"] == "Sun, 05 Jul 2026 12:00:00 GMT"


# ==============================================================================
# 5. Google Fact Check Tests
# ==============================================================================

def test_google_fact_check_success(mocker):
    """Test searching Google's Fact Check claims API."""
    mocker.patch.dict(os.environ, {"GOOGLE_API_KEY": "test_google_key"})
    
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "claims": [
            {
                "text": "The moon is made of green cheese",
                "claimant": "Some User",
                "claimDate": "2026-07-01T00:00:00Z",
                "claimReview": [
                    {
                        "publisher": {"name": "FactCheck.org"},
                        "textualRating": "False"
                    }
                ]
            }
        ]
    }
    mocker.patch("requests.get", return_value=mock_response)

    tool = GoogleFactCheckTool()
    result = tool._run(query="moon green cheese")
    assert "moon is made of green cheese" in result
    assert "FactCheck.org" in result
    assert "False" in result
