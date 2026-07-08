"""Offline tests for the UnifiedRssTool OPML -> RssFeeds JSON pipeline."""

import json
from datetime import datetime, timedelta

from crewai_custom_tools.tools.web.rss_aggregator import UnifiedRssTool

_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <body>
    <outline text="AI Feed" type="rss" xmlUrl="https://rss.example/ai" htmlUrl="https://rss.example"/>
  </body>
</opml>"""


def _make_feed(mocker, *, recent: bool):
    """Build a MagicMock feedparser feed with a single dated entry."""
    feed = mocker.MagicMock()
    feed.bozo = False
    feed.status = 200
    entry = mocker.MagicMock()
    entry.get.side_effect = lambda key, default=None: {
        "title": "Recent AI News",
        "link": "https://rss.example/ai/1",
        "summary": "A short RSS summary.",
    }.get(key, default)
    when = datetime.now() - timedelta(days=1 if recent else 400)
    entry.published_parsed = when.timetuple()
    feed.entries = [entry]
    return feed


def test_unified_rss_writes_json_file(tmp_path, mocker):
    """When output_file_path is given, the RssFeeds JSON is written to it."""
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(_OPML)
    out_file = tmp_path / "sub" / "report.json"  # nested dir must be created
    mocker.patch("feedparser.parse", return_value=_make_feed(mocker, recent=True))

    result = UnifiedRssTool()._run(
        opml_file_path=str(opml_file), days=7, output_file_path=str(out_file)
    )

    assert json.loads(result)["success"] is True
    assert out_file.exists()
    written = json.loads(out_file.read_text())
    assert list(written.keys()) == ["rss_feeds"]
    feed = written["rss_feeds"][0]
    assert feed["feed_url"] == "https://rss.example/ai"
    article = feed["articles"][0]
    assert article["title"] == "Recent AI News"
    assert article["link"] == "https://rss.example/ai/1"
    # No scraper yet (stub returns None) -> content falls back to the RSS summary.
    assert article["content"] == "A short RSS summary."


def test_unified_rss_positional_signature_matches_consumer(tmp_path, mocker):
    """rss_utils calls ._run(opml, days, output) positionally — that contract must hold."""
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(_OPML)
    out_file = tmp_path / "report.json"
    mocker.patch("feedparser.parse", return_value=_make_feed(mocker, recent=True))

    UnifiedRssTool()._run(str(opml_file), 7, str(out_file))  # exact positional call
    assert out_file.exists()


def test_unified_rss_filters_old_articles(tmp_path, mocker):
    """Entries older than `days` are dropped; the written feed list is then empty."""
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(_OPML)
    out_file = tmp_path / "report.json"
    mocker.patch("feedparser.parse", return_value=_make_feed(mocker, recent=False))

    payload = json.loads(UnifiedRssTool()._run(str(opml_file), 7, str(out_file)))
    assert payload["success"] is True
    assert payload["data"]["feeds"] == 0
    assert json.loads(out_file.read_text())["rss_feeds"] == []
