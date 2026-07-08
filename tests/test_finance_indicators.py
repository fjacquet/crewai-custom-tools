"""Tests for the ported finwiz finance tools (Twelve Data, AV news, Chart-img, Perplexity)."""

import json
import os

import requests

from crewai_custom_tools.tools.finance.indicators import (
    TwelveDataIndicatorTool,
    TwelveDataMultiIndicatorTool,
)
from crewai_custom_tools.tools.finance.market_extras import (
    AlphaVantageNewsSentimentTool,
    ChartImgTool,
)
from crewai_custom_tools.tools.web.perplexity_structured import PerplexityStructuredTool


def _envelope(result):
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


def _mock_response(mocker, *, json_data=None, content=b"", headers=None):
    resp = mocker.MagicMock()
    resp.raise_for_status.return_value = None
    if json_data is not None:
        resp.json.return_value = json_data
    resp.content = content
    resp.headers = headers or {}
    return resp


# --- Twelve Data ---------------------------------------------------------------


def test_twelve_data_indicator_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _envelope(TwelveDataIndicatorTool()._run(symbol="AAPL", indicator="rsi"))
    assert payload["success"] is False
    assert "TWELVE_DATA_API_KEY" in payload["error"]


def test_twelve_data_indicator_success(mocker):
    mocker.patch.dict(os.environ, {"TWELVE_DATA_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_mock_response(mocker, json_data={"values": [{"rsi": "55"}]}),
    )
    payload = _envelope(TwelveDataIndicatorTool()._run(symbol="AAPL", indicator="rsi", length=14))
    assert payload["success"] is True
    assert payload["data"]["values"][0]["rsi"] == "55"


def test_twelve_data_indicator_api_error(mocker):
    mocker.patch.dict(os.environ, {"TWELVE_DATA_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_mock_response(mocker, json_data={"status": "error", "message": "bad symbol"}),
    )
    payload = _envelope(TwelveDataIndicatorTool()._run(symbol="ZZ", indicator="rsi"))
    assert payload["success"] is False
    assert "bad symbol" in payload["error"]


def test_twelve_data_multi_indicator_success(mocker):
    mocker.patch.dict(os.environ, {"TWELVE_DATA_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_mock_response(mocker, json_data={"values": [{"v": 1}]}),
    )
    payload = _envelope(TwelveDataMultiIndicatorTool()._run(symbol="AAPL"))
    assert payload["success"] is True
    assert set(payload["data"]["indicators"]) == {"rsi", "macd", "bbands"}


def test_twelve_data_multi_indicator_partial_failure(mocker):
    mocker.patch.dict(os.environ, {"TWELVE_DATA_API_KEY": "k"})
    mocker.patch("requests.get", side_effect=requests.exceptions.ConnectionError("boom"))
    payload = _envelope(TwelveDataMultiIndicatorTool()._run(symbol="AAPL", indicators=["rsi"]))
    # The tool as a whole succeeds; the per-indicator error is captured inline.
    assert payload["success"] is True
    assert "error" in payload["data"]["indicators"]["rsi"]


# --- Alpha Vantage news sentiment ---------------------------------------------


def test_av_news_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _envelope(AlphaVantageNewsSentimentTool()._run(tickers="AAPL"))
    assert payload["success"] is False


def test_av_news_success(mocker):
    mocker.patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_mock_response(mocker, json_data={"feed": [{"title": "x"}]}),
    )
    payload = _envelope(AlphaVantageNewsSentimentTool()._run(tickers="AAPL"))
    assert payload["success"] is True
    assert payload["data"]["feed"][0]["title"] == "x"


def test_av_news_rate_limited(mocker):
    mocker.patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_mock_response(mocker, json_data={"Note": "rate limit"}),
    )
    payload = _envelope(AlphaVantageNewsSentimentTool()._run(tickers="AAPL"))
    assert payload["success"] is False
    assert "rate limit" in payload["error"]


# --- Chart-img -----------------------------------------------------------------


def test_chart_img_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _envelope(ChartImgTool()._run(symbol="AAPL"))
    assert payload["success"] is False


def test_chart_img_success(mocker):
    mocker.patch.dict(os.environ, {"CHART_IMG_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_mock_response(
            mocker, content=b"\x89PNG", headers={"Content-Type": "image/png"}
        ),
    )
    payload = _envelope(ChartImgTool()._run(symbol="AAPL"))
    assert payload["success"] is True
    assert payload["data"]["data_url"].startswith("data:image/png;base64,")


# --- Perplexity structured -----------------------------------------------------


def test_perplexity_structured_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _envelope(PerplexityStructuredTool()._run(prompt="hi"))
    assert payload["success"] is False


def test_perplexity_structured_text(mocker):
    mocker.patch.dict(os.environ, {"PERPLEXITY_API_KEY": "k"})
    mocker.patch(
        "requests.post",
        return_value=_mock_response(
            mocker,
            json_data={
                "choices": [{"message": {"content": "an answer"}}],
                "citations": ["http://a"],
            },
        ),
    )
    payload = _envelope(PerplexityStructuredTool()._run(prompt="hi"))
    assert payload["success"] is True
    assert payload["data"]["content"] == "an answer"


def test_perplexity_structured_json_schema(mocker):
    mocker.patch.dict(os.environ, {"PERPLEXITY_API_KEY": "k"})
    mocker.patch(
        "requests.post",
        return_value=_mock_response(
            mocker,
            json_data={"choices": [{"message": {"content": '{"n": 1}'}}]},
        ),
    )
    payload = _envelope(
        PerplexityStructuredTool()._run(prompt="hi", json_schema={"type": "object"})
    )
    assert payload["success"] is True
    assert payload["data"]["structured"] == {"n": 1}
