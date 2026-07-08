"""Tests for the fresh finance-analytics tools: screening, risk scoring, SEC EDGAR."""

import json

import pandas as pd

from crewai_custom_tools import (
    EnhancedSECAnalysisTool,
    MarketScreeningTool,
    StandardizedRiskScoringTool,
)


def _env(result):
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --------------------------------------------------------------------------- #
# MarketScreeningTool
# --------------------------------------------------------------------------- #
def _fake_ticker_factory(infos):
    class _FakeTicker:
        def __init__(self, symbol):
            self._info = infos.get(symbol, {})

        @property
        def info(self):
            return self._info

    return _FakeTicker


def test_screening_excludes_non_matching(mocker):
    infos = {
        "AAA": {"shortName": "Alpha", "sector": "Technology", "marketCap": 5e11,
                "trailingPE": 20, "averageVolume": 1e7},
        "BBB": {"shortName": "Beta", "sector": "Energy", "marketCap": 1e9,
                "trailingPE": 40, "averageVolume": 1e6},
    }
    mocker.patch(
        "crewai_custom_tools.tools.finance.screening.yf.Ticker",
        _fake_ticker_factory(infos),
    )
    payload = _env(
        MarketScreeningTool()._run(tickers=["AAA", "BBB"], min_market_cap=1e11, max_pe=30)
    )
    assert payload["success"] is True
    assert [m["symbol"] for m in payload["data"]["matches"]] == ["AAA"]
    assert payload["data"]["screened"] == 2


def test_screening_missing_field_fails_filter(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.finance.screening.yf.Ticker",
        _fake_ticker_factory({"CCC": {"shortName": "Gamma"}}),  # no marketCap
    )
    payload = _env(MarketScreeningTool()._run(tickers=["CCC"], min_market_cap=1e9))
    assert payload["data"]["matches"] == []


def test_screening_bad_ticker_is_skipped(mocker):
    def factory(symbol):
        if symbol == "BAD":
            raise ValueError("boom")

        class _T:
            info = {"shortName": "Good", "marketCap": 2e11}

        return _T()

    mocker.patch("crewai_custom_tools.tools.finance.screening.yf.Ticker", factory)
    payload = _env(MarketScreeningTool()._run(tickers=["GOOD", "BAD"]))
    assert payload["success"] is True
    assert payload["data"]["errored"] == ["BAD"]
    assert [m["symbol"] for m in payload["data"]["matches"]] == ["GOOD"]


# --------------------------------------------------------------------------- #
# StandardizedRiskScoringTool
# --------------------------------------------------------------------------- #
def _fake_risk_ticker(info, closes):
    class _T:
        def __init__(self, *a, **k):
            self.info = info

        def history(self, period="1y"):
            return pd.DataFrame({"Close": closes})

    return _T


def test_risk_score_full_factors(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.finance.risk.yf.Ticker",
        _fake_risk_ticker({"beta": 1.0, "debtToEquity": 60.0, "marketCap": 1e10},
                          [100 + i for i in range(60)]),
    )
    payload = _env(StandardizedRiskScoringTool()._run(ticker="xyz"))
    assert payload["success"] is True
    data = payload["data"]
    assert 0.0 <= data["risk_score"] <= 10.0
    assert all(data["factors"][f]["available"] for f in
               ("beta", "debt_to_equity", "volatility", "size"))


def test_risk_missing_factor_excluded(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.finance.risk.yf.Ticker",
        _fake_risk_ticker({"beta": 1.0}, [100, 100, 100]),  # no dte/marketCap
    )
    data = _env(StandardizedRiskScoringTool()._run(ticker="xyz"))["data"]
    assert data["factors"]["debt_to_equity"]["available"] is False
    assert data["factors"]["size"]["available"] is False
    assert data["factors"]["beta"]["available"] is True


def test_risk_no_factors_errors(mocker):
    class _T:
        info: dict = {}

        def history(self, period="1y"):
            return pd.DataFrame()

    mocker.patch("crewai_custom_tools.tools.finance.risk.yf.Ticker", lambda *a, **k: _T())
    payload = _env(StandardizedRiskScoringTool()._run(ticker="xyz"))
    assert payload["success"] is False
    assert "No risk factors" in payload["error"]


# --------------------------------------------------------------------------- #
# EnhancedSECAnalysisTool
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _sec_response(url, **kwargs):
    if "company_tickers" in url:
        return _Resp({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"}})
    if "submissions" in url:
        return _Resp({"name": "Apple Inc.", "sicDescription": "Electronics",
                      "filings": {"recent": {
                          "form": ["10-K", "8-K", "10-Q"],
                          "filingDate": ["2025-10-31", "2025-09-01", "2025-08-01"],
                          "reportDate": ["2025-09-27", "", "2025-06-30"],
                          "accessionNumber": ["0000320193-25-000079", "x",
                                              "0000320193-25-000060"],
                          "primaryDocument": ["aapl-20250927.htm", "y", "aapl-q3.htm"],
                      }}})
    if "companyfacts" in url:
        return _Resp({"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
            {"form": "10-K", "fp": "FY", "val": 112010000000, "end": "2025-09-27",
             "fy": 2025},
        ]}}}}})
    raise AssertionError(url)


def test_sec_success(mocker):
    mocker.patch("crewai_custom_tools.tools.finance.sec.requests.get",
                 side_effect=_sec_response)
    data = _env(EnhancedSECAnalysisTool()._run(ticker="aapl"))["data"]
    assert data["cik"] == 320193
    assert {f["form"] for f in data["recent_filings"]} <= {"10-K", "10-Q"}  # 8-K excluded
    assert data["latest_annual_financials"]["NetIncomeLoss"]["value"] == 112010000000
    assert data["recent_filings"][0]["url"].endswith(
        "/320193/000032019325000079/aapl-20250927.htm"
    )


def test_sec_unknown_ticker(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.finance.sec.requests.get",
        side_effect=lambda url, **kw: _sec_response(
            "https://www.sec.gov/files/company_tickers.json"
        ),
    )
    payload = _env(EnhancedSECAnalysisTool()._run(ticker="ZZZZ"))
    assert payload["success"] is False
    assert "No SEC CIK" in payload["error"]
