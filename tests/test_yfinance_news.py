import datetime
import json

import pytest

from crewai_custom_tools.tools.finance.yfinance_news import (
    GetTickerNewsInput,
    YahooFinanceNewsTool,
)


@pytest.fixture
def tool_instance():
    return YahooFinanceNewsTool()


@pytest.fixture(autouse=True)
def clear_cache():
    from crewai_custom_tools.config.cache import get_cache_manager

    get_cache_manager().clear()


def _data(result_str):
    payload = json.loads(result_str)
    assert payload["success"] is True, payload
    return payload["data"]


# --- Instantiation Tests ---
def test_instantiation(tool_instance):
    assert tool_instance.name == "Yahoo Finance News Tool"
    assert "Get recent news articles for stocks" in tool_instance.description
    assert tool_instance.args_schema == GetTickerNewsInput


# --- _run Method Tests (legacy flat schema still supported) ---
def test_run_successful_news_retrieval_with_limit(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    ticker_symbol = "GOODNEWS"
    limit = 2
    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance

    timestamp1 = int(datetime.datetime(2023, 1, 1, 10, 0, 0).timestamp())
    timestamp2 = int(datetime.datetime(2023, 1, 1, 12, 0, 0).timestamp())
    timestamp3 = int(datetime.datetime(2023, 1, 1, 14, 0, 0).timestamp())

    mock_ticker_instance.news = [
        {"title": "News 1", "publisher": "Pub A", "link": "link1.com", "providerPublishTime": timestamp1},
        {"title": "News 2", "publisher": "Pub B", "link": "link2.com", "providerPublishTime": timestamp2},
        {"title": "News 3", "publisher": "Pub C", "link": "link3.com", "providerPublishTime": timestamp3},
    ]

    data = _data(tool_instance._run(ticker=ticker_symbol, limit=limit))

    mock_yfinance_ticker.assert_called_once_with(ticker_symbol)
    assert data["ticker"] == ticker_symbol
    assert len(data["news"]) == limit
    assert data["news"][0]["title"] == "News 1"
    assert data["news"][0]["published_date"] == "2023-01-01 10:00"
    assert data["news"][1]["title"] == "News 2"


def test_run_nested_content_schema(tool_instance, mocker):
    """Modern yfinance nests fields under `content` (finding H5)."""
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    mock_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_instance
    mock_instance.news = [
        {
            "id": "1",
            "content": {
                "title": "Nested Title",
                "pubDate": "2026-07-01T10:00:00Z",
                "provider": {"displayName": "Reuters"},
                "canonicalUrl": {"url": "https://ex.com/a"},
            },
        }
    ]

    data = _data(tool_instance._run(ticker="NESTED", limit=5))
    item = data["news"][0]
    assert item["title"] == "Nested Title"
    assert item["publisher"] == "Reuters"
    assert item["link"] == "https://ex.com/a"
    assert item["published_date"] == "2026-07-01T10:00:00Z"


def test_run_successful_news_retrieval_fewer_than_limit(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance
    timestamp1 = int(datetime.datetime(2023, 2, 1, 10, 0, 0).timestamp())
    mock_ticker_instance.news = [
        {"title": "Only News", "publisher": "Pub X", "link": "link_only.com", "providerPublishTime": timestamp1}
    ]

    data = _data(tool_instance._run(ticker="FEWNEWS", limit=5))
    assert len(data["news"]) == 1
    assert data["news"][0]["title"] == "Only News"


def test_run_successful_news_retrieval_default_limit(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance
    mock_ticker_instance.news = [
        {"title": f"News {i}", "publisher": "Pub", "link": f"link{i}.com",
         "providerPublishTime": int(datetime.datetime.now().timestamp())}
        for i in range(7)
    ]

    data = _data(tool_instance._run(ticker="DEFAULTLIMITNEWS"))  # Default limit is 5
    assert len(data["news"]) == 5


def test_run_no_news_found(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance
    mock_ticker_instance.news = []

    data = _data(tool_instance._run(ticker="NONEWS"))
    assert data["news"] == []
    assert "No recent news found" in data["message"]


def test_run_news_item_missing_fields(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance
    mock_ticker_instance.news = [
        {"title": None, "publisher": "Pub D", "link": "link4.com", "providerPublishTime": None},
        {"title": "News E", "publisher": None, "link": None,
         "providerPublishTime": int(datetime.datetime.now().timestamp())},
    ]

    data = _data(tool_instance._run(ticker="MISSINGFIELDSNEWS", limit=2))
    assert len(data["news"]) == 2
    assert data["news"][0]["title"] == "No title"
    assert data["news"][0]["publisher"] == "Pub D"
    assert data["news"][0]["link"] == "link4.com"
    assert data["news"][0]["published_date"] == "Unknown date"
    assert data["news"][1]["title"] == "News E"
    assert data["news"][1]["publisher"] == "Unknown publisher"
    assert data["news"][1]["link"] == "#"


def test_run_yfinance_exception(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    ticker_symbol = "ERRORNEWS"
    error_message = "Test yfinance news error"

    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance
    type(mock_ticker_instance).news = property(
        mocker.MagicMock(side_effect=Exception(error_message))
    )

    payload = json.loads(tool_instance._run(ticker=ticker_symbol))
    assert payload["success"] is False
    assert error_message in payload["error"]

    # Error on Ticker instantiation
    mock_yfinance_ticker.reset_mock()
    mock_yfinance_ticker.side_effect = Exception(error_message)
    payload = json.loads(tool_instance._run(ticker=ticker_symbol))
    assert payload["success"] is False
    assert error_message in payload["error"]


def test_run_with_zero_limit(tool_instance, mocker):
    mock_yfinance_ticker = mocker.patch(
        "crewai_custom_tools.tools.finance.yfinance_news.yf.Ticker"
    )
    mock_ticker_instance = mocker.MagicMock()
    mock_yfinance_ticker.return_value = mock_ticker_instance
    mock_ticker_instance.news = [
        {"title": "News 1", "publisher": "Pub A", "link": "link1.com",
         "providerPublishTime": int(datetime.datetime.now().timestamp())}
    ]

    data = _data(tool_instance._run(ticker="ZEROLIMITNEWS", limit=0))
    assert data["ticker"] == "ZEROLIMITNEWS"
    assert len(data["news"]) == 0
