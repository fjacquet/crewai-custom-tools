"""Tests for the A+ Screening cluster: APlusScreeningTool, ScreeningCriteria,
ScreeningUtils, and ScreeningRanking (incl. the composite_score fallback
regression test — Wave 3 Task 4).

Ported from finwiz's ``tests/unit/tools/test_market_screening_tool.py``,
adapted to: this package's ``ok()``/``err()`` JSON envelope (finwiz's
``_run`` returned a raw dict); the rename ``MarketScreeningTool`` ->
``APlusScreeningTool`` / ``MarketScreeningInput`` -> ``APlusScreeningInput``
(this package already has a live-yfinance ``MarketScreeningTool`` in
``tools/finance/screening.py``); and the ``_utils``/``_criteria``/``_ranking``
component names, which are unchanged from finwiz.

Pure computation over a static symbol universe, no network — tests run
offline with direct inputs.
"""

import json
from datetime import datetime
from typing import Any

import pytest

from crewai_custom_tools.core.results import ok
from crewai_custom_tools.models.analytics_models import APlusScreeningInput, MarketScreeningResult
from crewai_custom_tools.tools.analytics.aplus_screening import APlusScreeningTool
from crewai_custom_tools.tools.analytics.screening_ranking import ScreeningCandidate, ScreeningRanking


def _env(result: str) -> dict[str, Any]:
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --------------------------------------------------------------------------- #
# Tool initialization & input schema
# --------------------------------------------------------------------------- #
def test_should_initialize_tool_correctly():
    tool = APlusScreeningTool()
    assert tool.name == "aplus_screening"
    assert "screens large universes" in tool.description.lower()
    assert tool.args_schema == APlusScreeningInput
    assert hasattr(tool, "_utils")
    assert hasattr(tool, "_criteria")
    assert hasattr(tool, "_ranking")


def test_should_validate_input_schema_correctly():
    valid_input = APlusScreeningInput(asset_type="etf", market_region="us", max_candidates=25, min_a_plus_score=0.9)
    assert valid_input.asset_type == "etf"
    assert valid_input.max_candidates == 25
    assert valid_input.min_a_plus_score == pytest.approx(0.9)

    with pytest.raises(ValueError):
        APlusScreeningInput(asset_type="invalid")

    with pytest.raises(ValueError):
        APlusScreeningInput(asset_type="stock", min_a_plus_score=1.5)

    with pytest.raises(ValueError):
        APlusScreeningInput(asset_type="crypto", max_candidates=1000)


# --------------------------------------------------------------------------- #
# End-to-end screening per asset type
# --------------------------------------------------------------------------- #
def test_should_screen_etf_universe_successfully():
    payload = _env(
        APlusScreeningTool()._run(asset_type="etf", market_region="us", max_candidates=10, min_a_plus_score=0.8)
    )
    data = payload["data"]
    assert "screening_result" in data
    assert "summary" in data
    assert "top_candidates" in data
    assert data["summary"]["asset_type"] == "etf"
    assert data["summary"]["total_screened"] > 0
    assert data["summary"]["candidates_found"] >= 0
    assert "success_rate" in data["summary"]


def test_should_screen_stock_universe_successfully():
    payload = _env(
        APlusScreeningTool()._run(asset_type="stock", market_region="us", max_candidates=15, min_a_plus_score=0.85)
    )
    data = payload["data"]
    assert data["summary"]["asset_type"] == "stock"
    assert data["summary"]["total_screened"] > 0


def test_should_screen_crypto_universe_successfully():
    payload = _env(
        APlusScreeningTool()._run(
            asset_type="crypto", market_region="global", max_candidates=20, min_a_plus_score=0.75
        )
    )
    data = payload["data"]
    assert data["summary"]["asset_type"] == "crypto"
    assert data["summary"]["total_screened"] > 0


# --------------------------------------------------------------------------- #
# Component-level: universe / criteria / market-data lookups
# --------------------------------------------------------------------------- #
def test_should_get_etf_universe_correctly():
    tool = APlusScreeningTool()
    us_universe = tool._utils._get_etf_universe("us")
    assert "SPY" in us_universe["symbols"]
    assert "VOO" in us_universe["symbols"]
    assert us_universe["count"] > 0

    eu_universe = tool._utils._get_etf_universe("eu")
    assert len(eu_universe["symbols"]) > 0

    global_universe = tool._utils._get_etf_universe("global")
    assert len(global_universe["symbols"]) >= len(us_universe["symbols"])


def test_should_get_stock_universe_correctly():
    tool = APlusScreeningTool()
    us_universe = tool._utils._get_stock_universe("us")
    assert "AAPL" in us_universe["symbols"]
    assert "MSFT" in us_universe["symbols"]


def test_should_get_crypto_universe_correctly():
    tool = APlusScreeningTool()
    crypto_universe = tool._utils._get_crypto_universe("global")
    assert "BTC" in crypto_universe["symbols"]
    assert "ETH" in crypto_universe["symbols"]


def test_should_get_default_screening_criteria_correctly():
    tool = APlusScreeningTool()
    etf_criteria = tool._criteria.get_default_criteria("etf")
    assert etf_criteria["max_expense_ratio"] == pytest.approx(0.25)
    assert etf_criteria["min_aum"] == 1e9

    stock_criteria = tool._criteria.get_default_criteria("stock")
    assert stock_criteria["min_roe"] == pytest.approx(0.20)

    crypto_criteria = tool._criteria.get_default_criteria("crypto")
    assert crypto_criteria["min_market_cap"] == 10e9


def test_should_get_etf_market_data_correctly():
    tool = APlusScreeningTool()
    spy_data = tool._utils._get_etf_market_data("SPY")
    assert spy_data["symbol"] == "SPY"
    assert spy_data["expense_ratio"] < 0.1

    unknown_data = tool._utils._get_etf_market_data("UNKNOWN")
    assert unknown_data["expense_ratio"] == pytest.approx(0.20)


def test_should_apply_stock_screening_filters_correctly():
    tool = APlusScreeningTool()
    good_stock_data = {
        "symbol": "QUALITY",
        "roe": 0.25,
        "revenue_growth": 0.18,
        "debt_to_equity": 0.2,
        "market_cap": 50e9,
        "fcf_positive": True,
        "fcf_growing": True,
    }
    criteria = tool._criteria.get_default_criteria("stock")
    assert tool._criteria._passes_stock_filters(good_stock_data, criteria) is True

    bad_stock_data = {
        "symbol": "POOR",
        "roe": 0.05,
        "revenue_growth": 0.02,
        "debt_to_equity": 0.8,
        "market_cap": 100e6,
        "fcf_positive": False,
        "fcf_growing": False,
    }
    assert tool._criteria._passes_stock_filters(bad_stock_data, criteria) is False


def test_should_calculate_preliminary_scores_correctly():
    tool = APlusScreeningTool()
    good_etf_data = {"expense_ratio": 0.03, "aum": 300e9, "tracking_error": 0.0008, "history_years": 15}
    assert tool._ranking._score_etf_preliminary(good_etf_data) > 0.8

    good_stock_data = {
        "roe": 0.30, "revenue_growth": 0.20, "debt_to_equity": 0.15,
        "market_cap": 200e9, "fcf_positive": True, "fcf_growing": True,
    }
    assert tool._ranking._score_stock_preliminary(good_stock_data) > 0.8

    good_crypto_data = {
        "market_cap": 500e9, "daily_volume": 10e9, "age_months": 100,
        "institutional_adoption": True, "real_utility": True,
    }
    assert tool._ranking._score_crypto_preliminary(good_crypto_data) > 0.8


def test_should_generate_screening_rationale_correctly():
    tool = APlusScreeningTool()
    good_data = {"symbol": "TEST", "name": "Test Investment", "expense_ratio": 0.05, "aum": 100e9}
    rationale = tool._utils.generate_screening_rationale(good_data, "etf", 0.95, True)
    assert "qualifies as A+ candidate" in rationale
    assert "TEST" in rationale


# --------------------------------------------------------------------------- #
# Custom criteria, candidate limiting, market regions
# --------------------------------------------------------------------------- #
def test_should_handle_custom_screening_criteria():
    custom_criteria = {"max_expense_ratio": 0.10, "min_aum": 5e9}
    payload = _env(
        APlusScreeningTool()._run(
            asset_type="etf", screening_criteria=custom_criteria, market_region="us", max_candidates=5
        )
    )
    assert payload["data"]["summary"]["candidates_found"] >= 0


def test_should_limit_candidates_correctly():
    payload = _env(APlusScreeningTool()._run(asset_type="etf", max_candidates=3, min_a_plus_score=0.0))
    assert len(payload["data"]["top_candidates"]) <= 3


def test_should_handle_different_market_regions():
    tool = APlusScreeningTool()
    us_result = _env(tool._run(asset_type="stock", market_region="us"))
    eu_result = _env(tool._run(asset_type="stock", market_region="eu"))
    global_result = _env(tool._run(asset_type="stock", market_region="global"))

    assert us_result["data"]["summary"]["total_screened"] > 0
    assert eu_result["data"]["summary"]["total_screened"] > 0
    assert global_result["data"]["summary"]["total_screened"] >= us_result["data"]["summary"]["total_screened"]


def test_should_sort_candidates_by_score():
    payload = _env(APlusScreeningTool()._run(asset_type="stock", max_candidates=5, min_a_plus_score=0.0))
    top_candidates = payload["data"]["top_candidates"]
    if len(top_candidates) > 1:
        scores = [c["score"] for c in top_candidates]
        assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
def test_should_handle_errors_gracefully(mocker):
    payload = _env(APlusScreeningTool()._run(asset_type="invalid"))
    assert payload["success"] is False
    assert payload["data"]["candidates_found"] == 0

    tool = APlusScreeningTool()
    mocker.patch.object(tool, "_apply_screening_filters", side_effect=Exception("Test error"))
    payload = _env(tool._run(asset_type="etf"))
    assert payload["success"] is False


def test_should_use_caching_efficiently():
    tool = APlusScreeningTool()
    data1 = tool._utils.get_basic_market_data("SPY", "etf")
    data2 = tool._utils.get_basic_market_data("SPY", "etf")
    assert data1 == data2


def test_should_handle_empty_screening_results():
    payload = _env(
        APlusScreeningTool()._run(
            asset_type="etf", screening_criteria={"max_expense_ratio": 0.001}, min_a_plus_score=0.99
        )
    )
    data = payload["data"]
    assert data["summary"]["candidates_found"] >= 0
    assert data["summary"]["a_plus_candidates"] >= 0


# --------------------------------------------------------------------------- #
# Pydantic model validation
# --------------------------------------------------------------------------- #
def test_should_validate_screening_candidate_model():
    valid_candidate = ScreeningCandidate(
        symbol="TEST",
        name="Test Investment",
        asset_type="etf",
        preliminary_score=0.85,
        meets_a_plus_criteria=True,
        screening_rationale="Test rationale",
        data_source="Test Source",
        screened_at=datetime.now(),
    )
    assert valid_candidate.preliminary_score == pytest.approx(0.85)

    with pytest.raises(ValueError):
        ScreeningCandidate(
            symbol="TEST",
            name="Test Investment",
            asset_type="etf",
            preliminary_score=1.5,  # Invalid: > 1.0
            meets_a_plus_criteria=True,
            screening_rationale="Test rationale",
            data_source="Test Source",
            screened_at=datetime.now(),
        )


def test_should_validate_market_screening_result_model():
    candidates = [
        ScreeningCandidate(
            symbol="TEST1",
            name="Test 1",
            asset_type="etf",
            preliminary_score=0.9,
            meets_a_plus_criteria=True,
            screening_rationale="Good ETF",
            data_source="Test",
            screened_at=datetime.now(),
        )
    ]

    result = MarketScreeningResult(
        asset_type="etf",
        screening_criteria={"max_expense_ratio": 0.25},
        market_region="us",
        total_screened=100,
        candidates_found=1,
        a_plus_candidates=1,
        candidates=candidates,
        screening_timestamp=datetime.now(),
        data_sources=["Test Source"],
    )
    assert result.total_screened == 100
    assert len(result.candidates) == 1
    # Port note: these two fields were silently dropped in finwiz's original
    # schema (missing declarations) — see analytics_models.py docstring.
    assert result.screening_timestamp is not None
    assert result.data_sources == ["Test Source"]


# --------------------------------------------------------------------------- #
# composite_score fallback bug — regression tests (Wave 3 Task 4)
#
# finwiz's ScreeningRanking.score_candidates detailed-analysis path read
# score_result.get("composite_score", 0.5) off the scorer's raw dict, but
# the scorer only ever nested that value under analysis_summary.composite_score
# — so the fallback ALWAYS fired, regardless of the real score. Pinned here at
# two levels: the ScreeningRanking unit directly, and end-to-end through the
# tool's _run.
# --------------------------------------------------------------------------- #
def test_regression_score_candidates_reads_real_composite_score_not_fallback(mocker):
    """A candidate with a known composite score != 0.5 must not score 0.5."""
    ranking = ScreeningRanking()
    known_composite_score = 0.9123  # deliberately far from the 0.5 fallback
    mocker.patch.object(
        ranking._a_plus_scorer,
        "_run",
        return_value=ok({"composite_score": known_composite_score, "is_a_plus_candidate": True, "grade": "A+"}),
    )

    candidates = [{"symbol": "PIN", "market_data": {"name": "Pin Corp", "roe": 0.3}}]
    scored = ranking.score_candidates(candidates, "stock", min_score=0.85, detailed_analysis=True)

    assert len(scored) == 1
    assert scored[0].preliminary_score == pytest.approx(known_composite_score)
    assert scored[0].preliminary_score != pytest.approx(0.5)


def test_regression_score_candidates_falls_back_to_half_only_on_genuine_envelope_failure(mocker):
    """The 0.5 fallback should still fire — but only when the envelope itself fails."""
    ranking = ScreeningRanking()
    mocker.patch.object(ranking._a_plus_scorer, "_run", return_value="not valid json")

    candidates = [{"symbol": "BROKEN", "market_data": {"name": "Broken Corp"}}]
    scored = ranking.score_candidates(candidates, "stock", min_score=0.85, detailed_analysis=True)

    assert len(scored) == 1
    assert scored[0].preliminary_score == pytest.approx(0.5)


def test_regression_end_to_end_detailed_screening_uses_real_composite_score(mocker):
    """End-to-end through APlusScreeningTool with include_detailed_analysis=True."""
    tool = APlusScreeningTool()
    known_composite_score = 0.8842
    mocker.patch.object(
        tool._ranking._a_plus_scorer,
        "_run",
        return_value=ok({"composite_score": known_composite_score, "is_a_plus_candidate": False, "grade": "A"}),
    )

    payload = _env(tool._run(asset_type="etf", max_candidates=1, min_a_plus_score=0.0, include_detailed_analysis=True))
    top_candidates = payload["data"]["top_candidates"]
    assert len(top_candidates) >= 1
    assert top_candidates[0]["score"] == pytest.approx(known_composite_score)
    assert top_candidates[0]["score"] != pytest.approx(0.5)
