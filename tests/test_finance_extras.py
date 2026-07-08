"""Offline tests for the Phase 2b finance-extra tools (envelope contract)."""

import json

import pandas as pd

from crewai_custom_tools.tools.finance import coinmarketcap_extras as cmc
from crewai_custom_tools.tools.finance.coinmarketcap_extras import (
    CoinMarketCapHistoricalTool,
    CoinMarketCapListTool,
    CoinMarketCapNewsTool,
)
from crewai_custom_tools.tools.finance.enhanced import (
    DeFiMetricsTool,
    EnhancedCryptoAnalysisTool,
    EnhancedETFAnalysisTool,
    TickerExistenceValidationTool,
)


def _payload(result):
    data = json.loads(result)
    assert set(data) == {"success", "data", "error"}
    return data


def _resp(mocker, *, json_data=None, status=200):
    r = mocker.MagicMock()
    r.status_code = status
    r.json.return_value = json_data or {}
    return r


# --- CoinMarketCap extras ---------------------------------------------------


def test_cmc_list_missing_key(mocker):
    mocker.patch.object(cmc, "_cmc_key", return_value=None)
    payload = _payload(CoinMarketCapListTool()._run())
    assert payload["success"] is False
    assert "API key" in payload["error"]


def test_cmc_list_success(mocker):
    mocker.patch.object(cmc, "_cmc_key", return_value="k")
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "data": [
                    {
                        "cmc_rank": 1,
                        "name": "Bitcoin",
                        "symbol": "BTC",
                        "quote": {"USD": {"price": 65000, "market_cap": 1.2e12, "volume_24h": 3e10}},
                    }
                ]
            },
        ),
    )
    payload = _payload(CoinMarketCapListTool()._run(limit=1))
    assert payload["success"] is True
    assert payload["data"]["cryptocurrencies"][0]["symbol"] == "BTC"


def test_cmc_news_success(mocker):
    mocker.patch.object(cmc, "_cmc_key", return_value="k")
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={"data": [{"title": "Hi", "source": {"name": "CMC"}, "url": "http://x"}]},
        ),
    )
    payload = _payload(CoinMarketCapNewsTool()._run(symbol="BTC"))
    assert payload["data"]["count"] == 1
    assert payload["data"]["articles"][0]["source"] == "CMC"


def test_cmc_historical_success(mocker):
    mocker.patch.object(cmc, "_cmc_key", return_value="k")
    mocker.patch(
        "requests.get",
        side_effect=[
            _resp(mocker, json_data={"data": [{"id": 1}]}),
            _resp(
                mocker,
                json_data={"data": {"quotes": [{"timestamp": "t", "quote": {"USD": {"price": 10}}}]}},
            ),
        ],
    )
    payload = _payload(CoinMarketCapHistoricalTool()._run(symbol="BTC"))
    assert payload["data"]["historical_data"][0]["price_usd"] == 10


def test_cmc_historical_unknown_symbol(mocker):
    mocker.patch.object(cmc, "_cmc_key", return_value="k")
    mocker.patch("requests.get", return_value=_resp(mocker, json_data={"data": []}))
    payload = _payload(CoinMarketCapHistoricalTool()._run(symbol="ZZZZ"))
    assert payload["success"] is False


# --- Ticker validation ------------------------------------------------------


def test_ticker_validation_etf(mocker):
    ticker = mocker.MagicMock()
    ticker.info = {"quoteType": "ETF", "exchange": "PCX", "longName": "Vanguard S&P 500", "currency": "USD"}
    mocker.patch("yfinance.Ticker", return_value=ticker)
    payload = _payload(TickerExistenceValidationTool()._run("VOO"))
    assert payload["data"]["valid"] is True
    assert payload["data"]["asset_class"] == "etf"


def test_ticker_validation_crypto(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(mocker, json_data=[{"id": "BTC-USD"}, {"id": "ETH-USD"}]),
    )
    payload = _payload(TickerExistenceValidationTool()._run("BTC", asset_class="crypto"))
    assert payload["data"]["valid"] is True
    assert "BTC-USD" in payload["data"]["meta"]["pairs"]


# --- Enhanced ETF -----------------------------------------------------------


def test_enhanced_etf_success(mocker):
    funds = mocker.MagicMock()
    funds.top_holdings = pd.DataFrame(
        {"Name": ["Apple", "Microsoft"], "Holding Percent": [0.07, 0.06]},
        index=["AAPL", "MSFT"],
    )
    funds.sector_weightings = {"technology": 0.3}
    etf = mocker.MagicMock()
    etf.info = {"shortName": "SPDR S&P 500", "categoryName": "Large Blend", "annualReportExpenseRatio": 0.0009}
    etf.get_funds_data.return_value = funds
    mocker.patch("yfinance.Ticker", return_value=etf)

    payload = _payload(EnhancedETFAnalysisTool()._run("SPY"))
    assert payload["success"] is True
    holdings = payload["data"]["top_holdings"]
    assert holdings[0]["symbol"] == "AAPL"
    # 0.07 fraction normalised to 7.0 percent
    assert holdings[0]["weight"] == 7.0
    assert payload["data"]["concentration"]["top_n_weight_pct"] == 13.0


# --- Enhanced crypto --------------------------------------------------------


def test_enhanced_crypto_success(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "name": "Bitcoin",
                "categories": ["Cryptocurrency"],
                "market_data": {
                    "current_price": {"usd": 65000},
                    "market_cap": {"usd": 1.2e12},
                    "market_cap_rank": 1,
                    "price_change_percentage_24h": 2.0,
                    "max_supply": 21000000,
                },
            },
        ),
    )
    payload = _payload(EnhancedCryptoAnalysisTool()._run("BTC"))
    assert payload["success"] is True
    assert payload["data"]["risk_assessment"]["level"] in {"Low", "Medium", "High", "Very High"}
    assert payload["data"]["investment_thesis"]


def test_enhanced_crypto_not_found(mocker):
    mocker.patch("requests.get", return_value=_resp(mocker, status=404))
    payload = _payload(EnhancedCryptoAnalysisTool()._run("NOTACOIN"))
    assert payload["success"] is False
    assert "not found" in payload["error"]


# --- DeFi metrics -----------------------------------------------------------


def test_defi_metrics_success(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "name": "Uniswap",
                "category": "Dexes",
                "chains": ["Ethereum"],
                "tvl": [{"date": 1, "totalLiquidityUSD": 5.0e9}],
            },
        ),
    )
    payload = _payload(DeFiMetricsTool()._run("UNI"))
    assert payload["success"] is True
    assert payload["data"]["current_tvl_usd"] == 5.0e9
    assert payload["data"]["tvl_tier"].startswith("large")


def test_defi_metrics_not_found(mocker):
    mocker.patch("requests.get", return_value=_resp(mocker, status=404))
    payload = _payload(DeFiMetricsTool()._run("NOPE"))
    assert payload["success"] is False
