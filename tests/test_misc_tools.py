"""Tests for the Batch 2f-2 misc tools (Geoapify, TechStack, WikipediaProcessing,
RSS aggregators, DelegatingEmailSearch). All offline/mocked."""

import json
import os

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.osint.email_delegator import DelegatingEmailSearchTool
from crewai_custom_tools.tools.web.places import GeoapifyPlacesTool
from crewai_custom_tools.tools.web.rss_aggregator import RSSFeedTool, UnifiedRssTool
from crewai_custom_tools.tools.web.tech_stack import TechStackTool
from crewai_custom_tools.tools.web.wikipedia_processing import WikipediaProcessingTool


def _env(result):
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --- Geoapify -----------------------------------------------------------------

def test_geoapify_success(mocker):
    mocker.patch.dict(os.environ, {"GEOAPIFY_API_KEY": "k"})
    resp = mocker.MagicMock()
    resp.json.return_value = {"type": "FeatureCollection", "features": [{"id": 1}]}
    mocker.patch("crewai_custom_tools.tools.web.places.requests.get", return_value=resp)

    payload = _env(GeoapifyPlacesTool()._run(categories=["catering.restaurant"], limit=5))
    assert payload["success"] is True
    assert payload["data"]["features"] == [{"id": 1}]


def test_geoapify_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _env(GeoapifyPlacesTool()._run(limit=5))
    assert payload["success"] is False
    assert "GEOAPIFY_API_KEY" in payload["error"]


def test_geoapify_filter_requires_value(mocker):
    mocker.patch.dict(os.environ, {"GEOAPIFY_API_KEY": "k"})
    payload = _env(GeoapifyPlacesTool()._run(filter_type="circle"))
    assert payload["success"] is False
    assert "filter_value" in payload["error"]


# --- TechStack ----------------------------------------------------------------

def test_tech_stack_success(mocker):
    mocker.patch.dict(os.environ, {"SERPER_API_KEY": "k"})
    resp = mocker.MagicMock()
    resp.json.return_value = {
        "organic": [{"title": "BuiltWith", "snippet": "Site uses React and WordPress on Cloudflare"}]
    }
    mocker.patch("crewai_custom_tools.tools.web.tech_stack.requests.post", return_value=resp)

    payload = _env(TechStackTool()._run(domain="example.com", detailed=True))
    assert payload["success"] is True
    techs = payload["data"]["technologies"]
    assert "react" in techs and "wordpress" in techs and "cloudflare" in techs
    assert "cloudflare" in payload["data"]["by_category"]["hosting"]


def test_tech_stack_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _env(TechStackTool()._run(domain="example.com"))
    assert payload["success"] is False
    assert "SERPER_API_KEY" in payload["error"]


# --- WikipediaProcessing (reuses WikipediaArticleTool) ------------------------

def _fake_article(**responses):
    """Return a side_effect returning a given envelope per ArticleAction value."""
    def _side(*_args, **kwargs):
        action = str(kwargs["action"])
        return responses[action]
    return _side


def test_wiki_extract_key_facts(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.web.wikipedia_processing.WikipediaArticleTool._run",
        side_effect=_fake_article(get_summary=ok({"title": "Py", "summary": "Fact one. Fact two. Fact three."})),
    )
    payload = _env(WikipediaProcessingTool()._run(title="Py", action="extract_key_facts", count=2))
    assert payload["success"] is True
    assert "Fact one" in payload["data"]["key_facts"]
    assert "Fact three" not in payload["data"]["key_facts"]


def test_wiki_summarize_for_query_matched(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.web.wikipedia_processing.WikipediaArticleTool._run",
        side_effect=_fake_article(get_article=ok({"title": "Py", "content": "Python is great\nUnrelated line"})),
    )
    payload = _env(WikipediaProcessingTool()._run(title="Py", action="summarize_article_for_query", query="python"))
    assert payload["success"] is True
    assert payload["data"]["matched"] is True
    assert "Python is great" in payload["data"]["summary"]


def test_wiki_summarize_section_missing(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.web.wikipedia_processing.WikipediaArticleTool._run",
        side_effect=_fake_article(get_article=ok({"title": "Py", "content": "no such heading here"})),
    )
    payload = _env(
        WikipediaProcessingTool()._run(title="Py", action="summarize_article_section", section_title="History")
    )
    assert payload["success"] is False
    assert "History" in payload["error"]


def test_wiki_query_action_requires_query():
    payload = _env(WikipediaProcessingTool()._run(title="Py", action="summarize_article_for_query"))
    assert payload["success"] is False
    assert "query" in payload["error"]


# --- RSS aggregators (reuse RssFeedParserTool / OpmlParserTool) ---------------

def test_rss_feed_tool_aggregates(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.web.rss_aggregator.RssFeedParserTool._run",
        side_effect=lambda *a, **k: ok([{"title": "Headline", "link": "http://x", "published": "now", "summary": ""}]),
    )
    payload = _env(RSSFeedTool()._run(region="france", max_articles=3))
    assert payload["success"] is True
    assert payload["data"]["articles"]
    assert payload["data"]["articles"][0]["source"]  # source name attached


def test_rss_feed_tool_unknown_region():
    payload = _env(RSSFeedTool()._run(region="atlantis"))
    assert payload["success"] is False
    assert "atlantis" in payload["error"]


def test_unified_rss_tool_bad_opml(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.web.rss_aggregator.OpmlParserTool._run",
        side_effect=lambda *a, **k: err("OPML file not found at /nope"),
    )
    payload = _env(UnifiedRssTool()._run(opml_file_path="/nope"))
    assert payload["success"] is False


# --- DelegatingEmailSearch (routes to our Hunter/Serper tools) ----------------

def test_email_router_hunter(mocker):
    hunter = mocker.patch(
        "crewai_custom_tools.tools.osint.email_delegator.HunterIOTool._run",
        return_value=ok({"emails": []}),
    )
    payload = _env(DelegatingEmailSearchTool()._run(provider="hunter", query="example.com"))
    assert payload["success"] is True
    hunter.assert_called_once_with(domain="example.com")


def test_email_router_serper(mocker):
    serper = mocker.patch(
        "crewai_custom_tools.tools.osint.email_delegator.SerperEmailSearchTool._run",
        return_value=ok({"emails": []}),
    )
    _env(DelegatingEmailSearchTool()._run(provider="serper", query="Example Inc"))
    serper.assert_called_once_with(query="Example Inc")


def test_email_router_invalid_provider():
    payload = _env(DelegatingEmailSearchTool()._run(provider="bogus", query="x"))
    assert payload["success"] is False
    assert "bogus" in payload["error"]
