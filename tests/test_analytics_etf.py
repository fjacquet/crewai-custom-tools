"""Tests for the analytics ETF tool and its etf-metrics engine.

The tool is pure computation over caller-supplied inputs (no network),
so tests run offline with direct inputs — nothing to mock.
"""

import json

import pandas as pd
import pytest

from crewai_custom_tools.tools.analytics.etf_analysis import ETFAnalysisTool
from crewai_custom_tools.tools.analytics.etf_metrics import (
    calculate_concentration_risk,
    calculate_correlation,
    calculate_etf_efficiency_score,
    calculate_expense_impact,
    calculate_liquidity_score,
    calculate_tracking_error,
)


def _env(result):
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --------------------------------------------------------------------------- #
# Engine: calculate_tracking_error / calculate_correlation
# --------------------------------------------------------------------------- #
def test_tracking_error_on_identical_aligned_series_is_zero():
    returns = pd.Series([0.01, 0.02, -0.01, 0.015])
    assert calculate_tracking_error(returns, returns.copy(), annualize=True) == pytest.approx(0.0)


def test_tracking_error_annualization():
    etf = pd.Series([0.010, 0.020, -0.010, 0.015])
    bench = pd.Series([0.011, 0.019, -0.009, 0.014])
    daily = calculate_tracking_error(etf, bench, annualize=False)
    annual = calculate_tracking_error(etf, bench, annualize=True)
    assert daily == pytest.approx(float((etf - bench).std()))
    assert annual == pytest.approx(daily * (252**0.5))


def test_tracking_error_insufficient_data_returns_zero():
    assert calculate_tracking_error(pd.Series([0.01]), pd.Series([0.02])) == 0.0


def test_correlation_perfectly_correlated():
    etf = pd.Series([0.01, 0.02, 0.03, 0.04])
    assert calculate_correlation(etf, etf * 2) == pytest.approx(1.0)


def test_correlation_insufficient_data_returns_zero():
    assert calculate_correlation(pd.Series([0.01]), pd.Series([0.02])) == 0.0


# --------------------------------------------------------------------------- #
# Engine: calculate_expense_impact
# --------------------------------------------------------------------------- #
def test_expense_impact_math():
    returns = pd.Series([0.10, 0.10])  # avg annual return 10%
    impact = calculate_expense_impact(returns, expense_ratio=0.005, years=10)
    gross = 1.10**10
    net = 1.095**10
    assert impact["annual_drag"] == pytest.approx(0.005)
    assert impact["cumulative_cost"] == pytest.approx((gross - net) / gross)
    assert impact["years"] == 10


def test_expense_impact_empty_returns():
    impact = calculate_expense_impact(pd.Series([], dtype=float), expense_ratio=0.005)
    assert impact == {"annual_drag": 0.0, "cumulative_cost": 0.0, "return_reduction_pct": 0.0}


# --------------------------------------------------------------------------- #
# Engine: calculate_liquidity_score
# --------------------------------------------------------------------------- #
def test_liquidity_score_top_tier():
    score = calculate_liquidity_score(avg_daily_volume=50_000_000, bid_ask_spread_pct=0.01, market_cap=400_000_000_000)
    assert score["liquidity_score"] == pytest.approx(100.0)
    assert score["liquidity_rating"] == "Excellent"


def test_liquidity_score_bottom_tier():
    score = calculate_liquidity_score(avg_daily_volume=50_000, bid_ask_spread_pct=1.0, market_cap=50_000_000)
    assert score["liquidity_score"] == pytest.approx(20.0)
    assert score["liquidity_rating"] == "Poor"


# --------------------------------------------------------------------------- #
# Engine: calculate_concentration_risk
# --------------------------------------------------------------------------- #
def test_concentration_risk_exact_metrics():
    holdings = [{"weight": 0.5}, {"weight": 0.5}]
    risk = calculate_concentration_risk(holdings, top_n=10)
    assert risk["top_n_concentration"] == pytest.approx(1.0)
    assert risk["herfindahl_index"] == pytest.approx(0.5)
    assert risk["effective_n_holdings"] == pytest.approx(2.0)
    assert risk["concentration_rating"] == "Very High"
    assert risk["total_holdings"] == 2


def test_concentration_risk_low_rating():
    holdings = [{"weight": 0.01} for _ in range(100)]
    risk = calculate_concentration_risk(holdings, top_n=10)
    assert risk["top_n_concentration"] == pytest.approx(0.10)
    assert risk["concentration_rating"] == "Low"
    assert risk["effective_n_holdings"] == pytest.approx(100.0)


def test_concentration_risk_empty_holdings():
    risk = calculate_concentration_risk([])
    assert risk["concentration_rating"] == "Unknown"
    assert risk["top_n_concentration"] == 0.0


def test_concentration_risk_zero_weights_filtered():
    risk = calculate_concentration_risk([{"weight": 0.0}, {"ticker_only": 1.0}])
    assert risk["concentration_rating"] == "Unknown"


# --------------------------------------------------------------------------- #
# Engine: calculate_etf_efficiency_score
# --------------------------------------------------------------------------- #
def test_efficiency_score_composite_math():
    score = calculate_etf_efficiency_score(tracking_error=0.0015, expense_ratio=0.0020, liquidity_score=85.0)
    # tracking 100 * 0.4 + cost 80 * 0.3 + 85 * 0.3 = 40 + 24 + 25.5 = 89.5
    assert score["efficiency_score"] == pytest.approx(89.5)
    assert score["efficiency_rating"] == "Excellent"


def test_efficiency_score_poor_rating():
    score = calculate_etf_efficiency_score(tracking_error=0.05, expense_ratio=0.02, liquidity_score=20.0)
    # 20*0.4 + 20*0.3 + 20*0.3 = 20
    assert score["efficiency_score"] == pytest.approx(20.0)
    assert score["efficiency_rating"] == "Poor"


# --------------------------------------------------------------------------- #
# ETFAnalysisTool envelope behaviour
# --------------------------------------------------------------------------- #
def test_etf_tool_happy_path_full_analysis():
    payload = _env(
        ETFAnalysisTool()._run(
            ticker="SPY",
            etf_returns=[0.010, 0.020, -0.010, 0.015],
            benchmark_returns=[0.011, 0.019, -0.009, 0.014],
            expense_ratio=0.0009,
            avg_daily_volume=50_000_000,
            bid_ask_spread_pct=0.01,
            market_cap=400_000_000_000,
            holdings=[{"weight": 0.07}, {"weight": 0.06}, {"weight": 0.04}],
        )
    )
    assert payload["success"] is True
    assert payload["error"] is None
    data = payload["data"]
    assert data["ticker"] == "SPY"
    metrics = data["metrics"]
    assert {
        "tracking_error", "tracking_error_pct", "correlation", "expense_impact",
        "expense_ratio_pct", "liquidity", "concentration", "efficiency",
    } <= set(metrics)
    assert metrics["liquidity"]["liquidity_score"] == pytest.approx(100.0)
    # tracking_error ~1.83% annualized -> Poor; efficiency = 40*0.4 + 100*0.3 + 100*0.3 = 76
    assert data["ratings"]["tracking_error"] == "Poor"
    assert metrics["efficiency"]["efficiency_score"] == pytest.approx(76.0)
    assert data["summary"] == {
        "has_tracking_analysis": True,
        "has_expense_analysis": True,
        "has_liquidity_analysis": True,
        "has_concentration_analysis": True,
        "has_efficiency_score": True,
        "overall_rating": "Good",
    }


def test_etf_tool_partial_inputs_skip_sections():
    payload = _env(ETFAnalysisTool()._run(ticker="VTI", holdings=[{"weight": 0.05}, {"weight": 0.03}]))
    data = payload["data"]
    assert data["summary"]["has_tracking_analysis"] is False
    assert data["summary"]["has_concentration_analysis"] is True
    assert data["summary"]["has_efficiency_score"] is False
    assert data["summary"]["overall_rating"] == "Not calculated"


def test_etf_tool_error_envelope_on_invalid_input():
    # ticker is required by the schema
    payload = _env(ETFAnalysisTool()._run(etf_returns=[0.01, 0.02]))
    assert payload["success"] is False
    assert "ETF analysis failed" in payload["error"]
    assert payload["data"] == {"ticker": "unknown"}


def test_etf_tool_error_envelope_bad_type():
    payload = _env(ETFAnalysisTool()._run(ticker="SPY", expense_ratio="not-a-number"))
    assert payload["success"] is False
    assert payload["data"] == {"ticker": "SPY"}
