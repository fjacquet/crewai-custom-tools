"""Tests for the VADER-based sentiment tools."""

import json

from crewai_custom_tools.tools.finance.sentiment import (
    CrossAssetSentimentComparatorTool,
    StandardizedSentimentAnalysisTool,
)

BULLISH = "Stocks surged to record highs on blowout earnings and strong growth."
BEARISH = "Markets crashed amid a brutal recession, mass layoffs, and mounting losses."


def _data(result):
    payload = json.loads(result)
    assert payload["success"] is True, payload
    return payload["data"]


def test_sentiment_bullish_text():
    data = _data(StandardizedSentimentAnalysisTool()._run(text=BULLISH))
    assert data["compound"] > 0
    assert data["label"] == "Bullish"
    assert data["score_0_100"] > 50


def test_sentiment_bearish_text():
    data = _data(StandardizedSentimentAnalysisTool()._run(text=BEARISH))
    assert data["compound"] < 0
    assert data["label"] == "Bearish"
    assert data["score_0_100"] < 50


def test_sentiment_aggregates_list():
    data = _data(StandardizedSentimentAnalysisTool()._run(texts=[BULLISH, BEARISH]))
    assert data["count"] == 2
    assert len(data["per_text"]) == 2


def test_sentiment_requires_input():
    payload = json.loads(StandardizedSentimentAnalysisTool()._run())
    assert payload["success"] is False


def test_cross_asset_ranks_bullish_first():
    data = _data(
        CrossAssetSentimentComparatorTool()._run(
            assets={"AAA": [BULLISH], "BBB": [BEARISH]}
        )
    )
    assert data["ranking"] == ["AAA", "BBB"]
    assert data["most_bullish"] == "AAA"
    assert data["most_bearish"] == "BBB"


def test_cross_asset_requires_input():
    payload = json.loads(CrossAssetSentimentComparatorTool()._run(assets={}))
    assert payload["success"] is False
