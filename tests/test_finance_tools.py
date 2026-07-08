"""Mock-based unit tests for unified stock, crypto, and market tools."""

import base64
import json
import os

import pandas as pd

from crewai_custom_tools.tools.finance.company_info import YahooFinanceCompanyInfoTool
from crewai_custom_tools.tools.finance.crypto import (
    CoinMarketCapInfoTool,
    KrakenAssetListTool,
    KrakenTickerInfoTool,
)
from crewai_custom_tools.tools.finance.exchange_rate import ExchangeRateTool
from crewai_custom_tools.tools.finance.fear_greed import FearGreedTool
from crewai_custom_tools.tools.finance.history_holdings import (
    YahooFinanceETFHoldingsTool,
    YahooFinanceHistoryTool,
)
from crewai_custom_tools.tools.finance.market_data import (
    AlphaVantageOverviewTool,
    FREDMacroTool,
)


def _data(result_str):
    """Assert the result is a successful envelope and return its data payload."""
    payload = json.loads(result_str)
    assert payload["success"] is True, payload
    return payload["data"]


# ==============================================================================
# 1. Yahoo Finance Info, Holdings & History Tests
# ==============================================================================


def test_yfinance_company_info(mocker):
    """Test Yahoo Finance company profile lookup and cleaning."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {
        "longName": "Apple Inc.",
        "industry": "Consumer Electronics",
        "sector": "Technology",
        "website": "https://apple.com",
        "country": "United States",
        "fullTimeEmployees": 150000,
        "longBusinessSummary": "Designs and sells iPhones...",
        "totalRevenue": 380000000000,
        "profitMargins": 0.25,
        "marketCap": 3000000000000,
    }
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    data = _data(YahooFinanceCompanyInfoTool()._run(ticker="AAPL"))

    assert data["name"] == "Apple Inc."
    assert data["industry"] == "Consumer Electronics"
    assert data["financial_metrics"]["revenue"] == 380000000000


def test_yfinance_etf_holdings(mocker):
    """ETF holdings/sectors populate via the funds_data API (not the removed get_holdings)."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {
        "shortName": "Vanguard Total Stock Market",
        "categoryName": "Large Blend",
        "totalAssets": 1300000000000,
    }

    holdings_df = pd.DataFrame(
        [
            {"Name": "Microsoft Corp", "Holding Percent": 0.065},
            {"Name": "Apple Inc", "Holding Percent": 0.058},
        ],
        index=pd.Index(["MSFT", "AAPL"], name="Symbol"),
    )
    mock_funds = mocker.MagicMock()
    mock_funds.top_holdings = holdings_df
    mock_funds.sector_weightings = {"technology": 0.28, "financials": 0.13}
    mock_ticker.get_funds_data.return_value = mock_funds

    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    data = _data(YahooFinanceETFHoldingsTool()._run(ticker="VTI"))

    assert data["symbol"] == "VTI"
    assert data["asset_class"] == "Large Blend"
    assert len(data["top_holdings"]) == 2
    assert data["top_holdings"][0]["symbol"] == "MSFT"
    assert data["top_holdings"][0]["weight"] == 0.065
    assert data["sector_breakdown"]["technology"] == 0.28


def test_yfinance_etf_holdings_non_fund_ticker(mocker):
    """A ticker with no funds_data returns success with empty holdings, no crash."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {"shortName": "Apple Inc."}
    mock_ticker.get_funds_data.side_effect = Exception("not a fund")
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    data = _data(YahooFinanceETFHoldingsTool()._run(ticker="AAPL"))
    # Empty holdings list and empty sector dict are stripped from the output.
    assert "top_holdings" not in data
    assert "sector_breakdown" not in data
    assert data["symbol"] == "AAPL"


# ==============================================================================
# 2. CoinMarketCap and Kraken Cryptocurrency Tests
# ==============================================================================


def test_coinmarketcap_info_success(mocker):
    """Test CoinMarketCap quote retrieval and schema formatting."""
    mocker.patch.dict(os.environ, {"COINMARKETCAP_API_KEY": "test_cmc_key"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "BTC": {
                "name": "Bitcoin",
                "symbol": "BTC",
                "cmc_rank": 1,
                "quote": {
                    "USD": {
                        "price": 65000.0,
                        "market_cap": 1200000000000,
                        "percent_change_24h": 2.5,
                    }
                },
            }
        }
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(CoinMarketCapInfoTool()._run(symbol="BTC"))

    assert data["name"] == "Bitcoin"
    assert data["price_usd"] == 65000.0
    assert data["cmc_rank"] == 1


def test_coinmarketcap_missing_key_returns_error(mocker):
    """No API key => error envelope (not an empty success)."""
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = json.loads(CoinMarketCapInfoTool()._run(symbol="BTC"))
    assert payload["success"] is False
    assert "not configured" in payload["error"]


def test_kraken_ticker_info(mocker):
    """Test fetching crypto ticker from Kraken API."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "XXBTZUSD": {
                "a": ["65000.00000", "1", "1.000"],
                "b": ["64999.00000", "1", "1.000"],
                "c": ["65010.00000", "0.05000000"],
            }
        }
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(KrakenTickerInfoTool()._run(pair="XXBTZUSD"))

    assert "a" in data
    assert data["a"][0] == "65000.00000"


def test_kraken_ticker_api_error_returns_error(mocker):
    """A Kraken API error surfaces as an error envelope, not an empty object."""
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"error": ["EQuery:Unknown asset pair"], "result": {}}
    mocker.patch("requests.get", return_value=mock_response)

    payload = json.loads(KrakenTickerInfoTool()._run(pair="BOGUS"))
    assert payload["success"] is False
    assert "Kraken API error" in payload["error"]


# ==============================================================================
# 3. Market indicators & Sentiment Tests (FRED & CNN Fear/Greed)
# ==============================================================================


def test_fred_macro_success(mocker):
    """Test FRED macro economic indicators fetcher."""
    mocker.patch.dict(os.environ, {"FRED_API_KEY": "test_fred_key"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "observations": [{"date": "2026-07-01", "value": "5.25"}]
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(FREDMacroTool()._run(indicator="fed_rate"))

    assert data["indicator"] == "fed_rate"
    assert data["value"] == "5.25"
    assert data["date"] == "2026-07-01"


def test_fear_greed_sentiment_success(mocker):
    """Test scraping market-wide sentiment from CNN Fear & Greed index."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "fear_and_greed": {"score": 72.0, "rating": "greed", "previous_close": 70.0}
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(FearGreedTool()._run())

    assert data["score"] == 72.0
    assert data["sentiment"] == "Greed"
    assert data["previous_close_score"] == 70.0


def test_fear_greed_historical_keys(mocker):
    """Week/month/year fields read CNN's previous_1_* keys (finding M4)."""
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "fear_and_greed": {
            "score": 50.0,
            "rating": "neutral",
            "previous_close": 51.0,
            "previous_1_week": 45.0,
            "previous_1_month": 60.0,
            "previous_1_year": 30.0,
        }
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(FearGreedTool()._run())

    assert data["one_week_ago_score"] == 45.0
    assert data["one_month_ago_score"] == 60.0
    assert data["one_year_ago_score"] == 30.0


# ==============================================================================
# 4. Exchange Rates Tests
# ==============================================================================


def test_exchange_rates_success(mocker):
    """Exchange rates return a JSON envelope with a structured rates map."""
    mocker.patch.dict(os.environ, {"OPENEXCHANGERATES_API_KEY": "test_oer_key"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "base": "USD",
        "rates": {"EUR": 0.92, "GBP": 0.78, "JPY": 160.0},
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(ExchangeRateTool()._run(base_currency="USD", target_currencies=["EUR", "GBP"]))

    assert data["base"] == "USD"
    assert data["rates"]["EUR"] == 0.92
    assert "JPY" not in data["rates"]  # filtered to requested targets


# ==============================================================================
# 5. History, Kraken Balance, Alpha Vantage
# ==============================================================================


def test_yfinance_history_success(mocker):
    """Test Yahoo Finance Ticker History retrieval and statistics formatting."""
    mock_ticker = mocker.MagicMock()
    history_df = pd.DataFrame(
        [
            {"Open": 100.0, "High": 105.0, "Low": 99.0, "Close": 104.0, "Volume": 1000000},
            {"Open": 104.0, "High": 108.0, "Low": 103.0, "Close": 107.0, "Volume": 1500000},
        ],
        index=[pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-02")],
    )
    mock_ticker.history.return_value = history_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    data = _data(YahooFinanceHistoryTool()._run(ticker="AAPL"))

    assert data["summary"]["symbol"] == "AAPL"
    assert data["summary"]["start_date"] == "2026-07-01"
    assert data["summary"]["price_change"] == 3.0
    assert data["summary"]["price_change_percent"] == round((107 / 104 - 1) * 100, 2)
    assert len(data["history"]) == 2


def test_yfinance_history_zero_earliest_close(mocker):
    """A zero/missing earliest close yields price_change_percent=None (finding L1)."""
    mock_ticker = mocker.MagicMock()
    history_df = pd.DataFrame(
        [
            {"Open": 0.0, "High": 0.0, "Low": 0.0, "Close": 0.0, "Volume": 0},
            {"Open": 150.0, "High": 155.0, "Low": 149.0, "Close": 152.0, "Volume": 1000},
        ],
        index=[pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-02")],
    )
    mock_ticker.history.return_value = history_df
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    data = _data(YahooFinanceHistoryTool()._run(ticker="ZZ"))

    assert data["summary"]["price_change_percent"] is None


def test_kraken_asset_list_success(mocker):
    """Test private account balance asset listing using Kraken private REST mock."""
    mocker.patch.dict(
        os.environ,
        {
            "KRAKEN_API_KEY": "test_key",
            "KRAKEN_API_SECRET": base64.b64encode(b"test_secret").decode(),
        },
    )

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"ZUSD": "1000.50", "XXBT": "0.15000"}}
    mocker.patch("requests.post", return_value=mock_response)

    data = _data(KrakenAssetListTool()._run(asset_class="currency"))

    assert len(data) == 2
    assert data[0]["asset"] == "ZUSD"
    assert data[0]["quantity"] == 1000.50


def test_kraken_asset_list_filters_specific_asset(mocker):
    """A specific asset_class filters the returned balances client-side (finding L5)."""
    mocker.patch.dict(
        os.environ,
        {
            "KRAKEN_API_KEY": "test_key",
            "KRAKEN_API_SECRET": base64.b64encode(b"test_secret").decode(),
        },
    )
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"result": {"ZUSD": "1000.50", "XXBT": "0.15000"}}
    mocker.patch("requests.post", return_value=mock_response)

    data = _data(KrakenAssetListTool()._run(asset_class="XXBT"))

    assert len(data) == 1
    assert data[0]["asset"] == "XXBT"


def test_kraken_asset_list_missing_creds_returns_error(mocker):
    """Missing Kraken credentials return an error envelope."""
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = json.loads(KrakenAssetListTool()._run())
    assert payload["success"] is False
    assert "credentials" in payload["error"]


def test_alphavantage_overview_success(mocker):
    """Test fundamental company data retrieval from Alpha Vantage."""
    mocker.patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test_av_key"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Symbol": "MSFT",
        "Name": "Microsoft Corporation",
        "ReturnOnEquityTTM": "0.385",
        "DebtToEquityRatio": "0.45",
        "QuarterlyRevenueGrowthYOY": "0.12",
        "ProfitMargin": "0.26",
        "PERatio": "35.2",
    }
    mocker.patch("requests.get", return_value=mock_response)

    data = _data(AlphaVantageOverviewTool()._run(ticker="MSFT"))

    assert data["symbol"] == "MSFT"
    assert data["name"] == "Microsoft Corporation"
    assert data["return_on_equity_ttm"] == 0.385
    assert data["debt_to_equity_ratio"] == 0.45
