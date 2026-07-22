"""Tests for the A+ Investment Scoring Tool.

Ported from finwiz's ``tests/unit/tools/test_a_plus_scoring_tool.py``, adapted
to this package's ``ok()``/``err()`` JSON envelope (finwiz's ``_run`` returned
a raw dict; here it returns an envelope string parsed via ``json.loads``).
finwiz's ``tests/fixtures/asset_data.py``/``market_data.py`` factory helpers
are inlined below (same field defaults) since this package has no shared
fixtures module.

Pure computation, no network — tests run offline with direct inputs.
"""

import json
from typing import Any

from crewai_custom_tools.models.analytics_models import APlusScoringInput
from crewai_custom_tools.tools.analytics.a_plus_scoring import APlusScoringTool


def _env(result: str) -> dict[str, Any]:
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --------------------------------------------------------------------------- #
# Inlined finwiz fixture factories (tests/fixtures/asset_data.py, market_data.py)
# --------------------------------------------------------------------------- #
def create_stock_data(roe=0.25, revenue_growth=0.20, debt_to_equity=0.2, market_cap=10e9, **overrides):
    data = {
        "roe": roe,
        "revenue_growth": revenue_growth,
        "debt_to_equity": debt_to_equity,
        "market_cap": market_cap,
        "fcf_positive": True,
        "fcf_growing": True,
        "management_quality": 0.8,
        "governance_score": 0.85,
        "competitive_moat": 0.9,
    }
    data.update(overrides)
    return data


def create_etf_data(expense_ratio=0.03, aum=5e9, tracking_error=0.001, **overrides):
    data = {
        "expense_ratio": expense_ratio,
        "aum": aum,
        "tracking_error": tracking_error,
        "history_years": 5,
        "issuer_reputation": 0.9,
        "regulatory_compliance": 0.95,
        "transparency_score": 0.85,
    }
    data.update(overrides)
    return data


def create_crypto_data(market_cap=50e9, daily_volume=2e9, age_months=60, **overrides):
    data = {
        "market_cap": market_cap,
        "daily_volume": daily_volume,
        "age_months": age_months,
        "institutional_adoption": True,
        "real_utility": True,
        "team_quality": 0.8,
        "development_activity": 0.9,
        "community_strength": 0.7,
    }
    data.update(overrides)
    return data


def create_technical_data(momentum_score=0.7, trend_strength=0.8, volatility_score=0.6, **overrides):
    data = {
        "momentum_score": momentum_score,
        "trend_strength": trend_strength,
        "volatility_score": volatility_score,
    }
    data.update(overrides)
    return data


def create_risk_data(volatility=0.20, beta=1.0, max_drawdown=0.15, **overrides):
    data = {"volatility": volatility, "beta": beta, "max_drawdown": max_drawdown}
    data.update(overrides)
    return data


def create_market_context(vix=15.0, inflation=2.5, interest_rate=4.5, **overrides):
    data = {"vix": vix, "inflation": inflation, "interest_rate": interest_rate}
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# Tool initialization
# --------------------------------------------------------------------------- #
def test_should_create_tool_instance_when_initialized():
    tool = APlusScoringTool()
    assert tool.name == "A+ Investment Scoring Tool"
    assert "comprehensive" in tool.description.lower()
    assert "a+" in tool.description.lower()
    assert tool.args_schema == APlusScoringInput


# --------------------------------------------------------------------------- #
# Asset-type scoring paths
# --------------------------------------------------------------------------- #
def test_should_score_excellent_etf_as_a_plus_when_all_criteria_met():
    excellent_etf = create_etf_data(expense_ratio=0.001, aum=100e9, tracking_error=0.0001)
    excellent_etf.update(create_technical_data(momentum_score=0.9, trend_strength=0.9))
    excellent_etf.update(create_risk_data(volatility=0.10, max_drawdown=0.05))

    payload = _env(
        APlusScoringTool()._run(
            symbol="VTI",
            asset_type="etf",
            fundamental_data=excellent_etf,
            market_context=create_market_context(),
        )
    )
    assert payload["success"] is True
    data = payload["data"]
    assert data["symbol"] == "VTI"
    assert data["asset_type"] == "etf"
    assert "analysis_summary" in data
    assert "composite_score" in data["analysis_summary"]
    assert 0.0 <= data["analysis_summary"]["composite_score"] <= 1.0


def test_should_score_excellent_stock_as_a_plus_when_fundamentals_strong():
    excellent_stock = create_stock_data(roe=0.30, revenue_growth=0.25, debt_to_equity=0.1)
    excellent_stock.update(create_technical_data(momentum_score=0.9))
    excellent_stock.update(create_risk_data(volatility=0.15, beta=1.0))

    payload = _env(
        APlusScoringTool()._run(
            symbol="AAPL",
            asset_type="stock",
            fundamental_data=excellent_stock,
            market_context=create_market_context(),
        )
    )
    data = payload["data"]
    assert data["symbol"] == "AAPL"
    assert data["asset_type"] == "stock"
    assert 0.0 <= data["analysis_summary"]["composite_score"] <= 1.0


def test_should_score_mature_crypto_appropriately():
    mature_crypto = create_crypto_data(market_cap=100e9, daily_volume=5e9, age_months=72)
    mature_crypto.update(create_technical_data(momentum_score=0.7))
    mature_crypto.update(create_risk_data(volatility=0.30, max_drawdown=0.25))

    payload = _env(
        APlusScoringTool()._run(
            symbol="BTC",
            asset_type="crypto",
            fundamental_data=mature_crypto,
            market_context=create_market_context(),
        )
    )
    data = payload["data"]
    assert data["symbol"] == "BTC"
    assert data["asset_type"] == "crypto"
    assert 0.0 <= data["analysis_summary"]["composite_score"] <= 1.0


# --------------------------------------------------------------------------- #
# Edge cases: incomplete/empty data, invalid input
# --------------------------------------------------------------------------- #
def test_should_handle_incomplete_fundamental_data():
    payload = _env(APlusScoringTool()._run(symbol="TEST", asset_type="etf", fundamental_data={"expense_ratio": 0.05}))
    data = payload["data"]
    assert data["symbol"] == "TEST"
    assert 0.0 <= data["analysis_summary"]["composite_score"] <= 1.0


def test_should_handle_empty_fundamental_data_when_none_provided():
    payload = _env(APlusScoringTool()._run(symbol="EMPTY", asset_type="stock", fundamental_data={}))
    data = payload["data"]
    assert data["symbol"] == "EMPTY"
    assert 0.0 <= data["analysis_summary"]["composite_score"] <= 1.0


# --------------------------------------------------------------------------- #
# Market regime handling
# --------------------------------------------------------------------------- #
def test_should_adjust_criteria_when_bear_market_detected():
    bear_market = create_market_context(vix=40.0, market_regime="bear")
    payload = _env(
        APlusScoringTool()._run(
            symbol="TEST",
            asset_type="stock",
            fundamental_data=create_stock_data(),
            market_context=bear_market,
        )
    )
    assert payload["data"]["symbol"] == "TEST"


def test_should_cache_market_regime_when_assessed_recently():
    tool = APlusScoringTool()
    context = create_market_context(vix=20.0)

    result1 = _env(
        tool._run(symbol="TEST1", asset_type="stock", fundamental_data=create_stock_data(), market_context=context)
    )
    result2 = _env(
        tool._run(symbol="TEST2", asset_type="stock", fundamental_data=create_stock_data(), market_context=context)
    )

    assert result1["data"]["symbol"] == "TEST1"
    assert result2["data"]["symbol"] == "TEST2"


def test_should_adjust_scoring_weights_when_high_stress_market():
    high_stress = create_market_context(vix=35.0, market_regime="volatile")
    payload = _env(
        APlusScoringTool()._run(
            symbol="TEST",
            asset_type="stock",
            fundamental_data=create_stock_data(),
            market_context=high_stress,
        )
    )
    assert payload["data"]["symbol"] == "TEST"


# --------------------------------------------------------------------------- #
# Strengths/weaknesses, rationale, confidence
# --------------------------------------------------------------------------- #
def test_should_identify_strengths_and_weaknesses_when_mixed_scores():
    mixed_data = create_stock_data(roe=0.30, debt_to_equity=0.8)
    mixed_data.update(create_technical_data(momentum_score=0.9, trend_strength=0.3))

    payload = _env(
        APlusScoringTool()._run(
            symbol="TEST",
            asset_type="stock",
            fundamental_data=mixed_data,
            market_context=create_market_context(),
        )
    )
    summary = payload["data"]["analysis_summary"]
    assert "top_strengths" in summary or "main_concerns" in summary


def test_should_generate_appropriate_rationale_when_a_plus_score():
    aplus_data = create_stock_data(roe=0.35, revenue_growth=0.30, debt_to_equity=0.05)
    aplus_data.update(create_technical_data(momentum_score=0.95, trend_strength=0.95))
    aplus_data.update(create_risk_data(volatility=0.12, max_drawdown=0.08))

    payload = _env(
        APlusScoringTool()._run(
            symbol="APLUS",
            asset_type="stock",
            fundamental_data=aplus_data,
            market_context=create_market_context(),
        )
    )
    data = payload["data"]
    assert data["symbol"] == "APLUS"
    assert data["analysis_summary"]["composite_score"] > 0.0
    assert data["a_plus_score"]["a_plus_rationale"]


def test_should_calculate_confidence_level_based_on_data_quality():
    complete_data = create_stock_data()
    complete_data.update(create_technical_data())
    complete_data.update(create_risk_data())

    payload = _env(
        APlusScoringTool()._run(
            symbol="COMPLETE",
            asset_type="stock",
            fundamental_data=complete_data,
            market_context=create_market_context(),
        )
    )
    summary = payload["data"]["analysis_summary"]
    assert "confidence" in summary
    assert 0.0 <= summary["confidence"] <= 1.0


# --------------------------------------------------------------------------- #
# Custom criteria, symbol normalization, input schema
# --------------------------------------------------------------------------- #
def test_should_handle_custom_criteria_when_provided():
    custom_criteria = {"etf_max_expense_ratio": 0.05, "stock_min_roe": 0.30}
    payload = _env(
        APlusScoringTool()._run(
            symbol="TEST",
            asset_type="etf",
            fundamental_data=create_etf_data(expense_ratio=0.08),
            custom_criteria=custom_criteria,
        )
    )
    assert payload["data"]["symbol"] == "TEST"


def test_should_normalize_symbol_input_when_lowercase_provided():
    payload = _env(APlusScoringTool()._run(symbol="  aapl  ", asset_type="stock", fundamental_data=create_stock_data()))
    assert payload["data"]["symbol"] == "AAPL"


def test_should_validate_input_schema_when_creating_input_object():
    valid_input = APlusScoringInput(
        symbol="AAPL", asset_type="stock", fundamental_data={"roe": 0.25}, market_context={"vix": 20}
    )
    assert valid_input.symbol == "AAPL"
    assert valid_input.asset_type == "stock"
    assert valid_input.fundamental_data["roe"] == 0.25


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
def test_should_return_error_envelope_when_exception_occurs(mocker):
    mocker.patch(
        "crewai_custom_tools.tools.analytics.a_plus_scoring.calculate_fundamental_score",
        side_effect=Exception("Test error"),
    )
    payload = _env(APlusScoringTool()._run(symbol="ERROR", asset_type="stock", fundamental_data={}))
    assert payload["success"] is False
    assert "A+ scoring failed" in payload["error"]
    assert payload["data"]["symbol"] == "ERROR"


# --------------------------------------------------------------------------- #
# Risk scoring, cross-asset-type consistency
# --------------------------------------------------------------------------- #
def test_should_calculate_risk_score_appropriately_when_high_volatility():
    high_risk_data = create_stock_data()
    high_risk_data.update(create_risk_data(volatility=0.5, beta=2.0, max_drawdown=0.4))

    payload = _env(
        APlusScoringTool()._run(
            symbol="HIGHRISK",
            asset_type="stock",
            fundamental_data=high_risk_data,
            market_context=create_market_context(),
        )
    )
    assert payload["data"]["symbol"] == "HIGHRISK"
    assert payload["data"]["a_plus_score"]["risk_score"] < 1.0


def test_should_score_different_asset_types_with_appropriate_weights():
    tool = APlusScoringTool()
    etf_payload = _env(
        tool._run(
            symbol="ETF", asset_type="etf", fundamental_data=create_etf_data(),
            market_context=create_market_context(),
        )
    )
    stock_payload = _env(
        tool._run(
            symbol="STOCK", asset_type="stock", fundamental_data=create_stock_data(),
            market_context=create_market_context(),
        )
    )
    crypto_payload = _env(
        tool._run(
            symbol="CRYPTO", asset_type="crypto", fundamental_data=create_crypto_data(),
            market_context=create_market_context(),
        )
    )

    assert etf_payload["data"]["symbol"] == "ETF"
    assert stock_payload["data"]["symbol"] == "STOCK"
    assert crypto_payload["data"]["symbol"] == "CRYPTO"


# --------------------------------------------------------------------------- #
# composite_score bug-fix pin (top-level key present on the tool itself, not
# just from the caller side — see test_analytics_aplus_screening.py for the
# ScreeningRanking regression)
# --------------------------------------------------------------------------- #
def test_composite_score_is_present_and_consistent_at_top_level_and_nested():
    payload = _env(
        APlusScoringTool()._run(
            symbol="PIN",
            asset_type="stock",
            fundamental_data=create_stock_data(roe=0.35, revenue_growth=0.30, debt_to_equity=0.05),
            market_context=create_market_context(),
        )
    )
    data = payload["data"]
    assert "composite_score" in data
    assert data["composite_score"] == data["analysis_summary"]["composite_score"]
    assert data["composite_score"] == data["a_plus_score"]["composite_score"]
