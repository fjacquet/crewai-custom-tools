"""Tests for the analytics valuation tool and its price-targets engine.

The tool is pure computation over caller-supplied inputs (no network),
so tests run offline with direct inputs — nothing to mock.
"""

import json

import pandas as pd
import pytest

from crewai_custom_tools.tools.analytics.price_targets import (
    PriceTarget,
    calculate_consensus_target,
    calculate_dcf_target,
    calculate_pe_target,
    calculate_support_resistance_targets,
    calculate_technical_target,
)
from crewai_custom_tools.tools.analytics.valuation import ValuationTool


def _env(result):
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --------------------------------------------------------------------------- #
# Engine: calculate_dcf_target
# --------------------------------------------------------------------------- #
def test_dcf_zero_growth_exact_value():
    # With g=0: PV(CFs) = 100/1.1 + 100/1.21; TV = 100/0.10 = 1000; PV(TV) = 1000/1.21
    # Enterprise value works out to exactly 1000.0
    target = calculate_dcf_target(
        cash_flows=[100.0, 100.0], discount_rate=0.10, terminal_growth=0.0,
        shares_outstanding=100.0, current_price=8.0,
    )
    assert target.method == "dcf"
    assert target.target_price == pytest.approx(10.0)
    assert target.upside_pct == pytest.approx(25.0)
    assert target.confidence == pytest.approx(0.7)  # 2-year projection keeps base confidence
    assert target.assumptions["enterprise_value"] == pytest.approx(1000.0)


def test_dcf_rejects_rate_not_above_growth():
    target = calculate_dcf_target(cash_flows=[100.0], discount_rate=0.03, terminal_growth=0.03)
    assert target.target_price == 0.0
    assert target.confidence == 0.0


def test_dcf_no_cash_flows():
    target = calculate_dcf_target(cash_flows=[], discount_rate=0.10, terminal_growth=0.03)
    assert target.target_price == 0.0
    assert target.confidence == 0.0


def test_dcf_confidence_decays_with_projection_length():
    target = calculate_dcf_target(cash_flows=[100.0] * 8, discount_rate=0.10, terminal_growth=0.02)
    # base 0.7 minus 0.05 per year beyond 3: 0.7 - 5*0.05 = 0.45
    assert target.confidence == pytest.approx(0.45)


# --------------------------------------------------------------------------- #
# Engine: calculate_pe_target
# --------------------------------------------------------------------------- #
def test_pe_target_happy_path():
    target = calculate_pe_target(earnings_per_share=5.0, target_pe_ratio=20.0, current_price=80.0, sector_avg_pe=20.0)
    assert target.target_price == pytest.approx(100.0)
    assert target.upside_pct == pytest.approx(25.0)
    assert target.confidence == pytest.approx(0.65)  # no deviation from sector average


def test_pe_target_invalid_eps():
    target = calculate_pe_target(earnings_per_share=-1.0, target_pe_ratio=20.0)
    assert target.target_price == 0.0
    assert target.confidence == 0.0


# --------------------------------------------------------------------------- #
# Engine: calculate_technical_target / support-resistance
# --------------------------------------------------------------------------- #
def test_technical_target_insufficient_data():
    target = calculate_technical_target(pd.Series([100.0, 101.0]), method="fibonacci")
    assert target.target_price == 0.0
    assert target.confidence == 0.0


def test_technical_fibonacci_extension():
    prices = pd.Series([float(p) for p in range(100, 121)])  # swing_low=101 (tail 20), swing_high=120
    target = calculate_technical_target(prices, method="fibonacci", current_price=120.0)
    assert target.method == "technical_fibonacci"
    assert target.target_price == pytest.approx(120.0 + (120.0 - 101.0) * 0.618)
    assert target.confidence == pytest.approx(0.5)


def test_technical_unknown_method():
    prices = pd.Series([float(p) for p in range(100, 120)])
    target = calculate_technical_target(prices, method="astrology", current_price=110.0)
    assert target.confidence == 0.0
    assert target.target_price == pytest.approx(110.0)


def test_support_resistance_insufficient_data():
    targets = calculate_support_resistance_targets(pd.Series([100.0] * 5))
    assert targets["resistance"].target_price == 0.0
    assert targets["support"].target_price == 0.0


def test_support_resistance_defaults_without_levels():
    # Strictly increasing series: no local max above current, no local min below it is found
    prices = pd.Series([float(p) for p in range(100, 125)])
    targets = calculate_support_resistance_targets(prices, current_price=124.0)
    assert targets["resistance"].target_price == pytest.approx(124.0 * 1.10)
    assert targets["support"].method == "support_resistance"


# --------------------------------------------------------------------------- #
# Engine: calculate_consensus_target
# --------------------------------------------------------------------------- #
def test_consensus_empty_targets():
    consensus = calculate_consensus_target([])
    assert consensus.target_price == 0.0
    assert consensus.confidence == 0.0


def test_consensus_confidence_weighted():
    t1 = PriceTarget(target_price=100.0, current_price=90.0, confidence=0.6, method="dcf")
    t2 = PriceTarget(target_price=120.0, current_price=90.0, confidence=0.3, method="pe_multiple")
    consensus = calculate_consensus_target([t1, t2])
    # weights = 0.6/0.9, 0.3/0.9
    assert consensus.target_price == pytest.approx(100.0 * (2 / 3) + 120.0 * (1 / 3))
    assert consensus.method == "consensus"
    assert consensus.assumptions["methods"] == ["dcf", "pe_multiple"]


def test_consensus_skips_zero_targets():
    t1 = PriceTarget(target_price=0.0, confidence=0.0, method="dcf")
    t2 = PriceTarget(target_price=50.0, confidence=0.5, method="pe_multiple")
    consensus = calculate_consensus_target([t1, t2])
    assert consensus.target_price == pytest.approx(50.0)


# --------------------------------------------------------------------------- #
# ValuationTool envelope behaviour
# --------------------------------------------------------------------------- #
def test_valuation_tool_happy_path_all_methods():
    payload = _env(
        ValuationTool()._run(
            ticker="AAPL",
            current_price=150.0,
            cash_flows=[100.0, 110.0, 121.0, 133.0],
            discount_rate=0.10,
            terminal_growth=0.03,
            shares_outstanding=10.0,
            earnings_per_share=6.5,
            target_pe_ratio=25.0,
            sector_avg_pe=24.0,
            price_history=[140.0 + i for i in range(25)],
        )
    )
    assert payload["success"] is True
    assert payload["error"] is None
    data = payload["data"]
    assert data["ticker"] == "AAPL"
    valuations = data["valuations"]
    assert set(valuations) == {"dcf", "pe_multiple", "technical_fibonacci", "support_resistance", "consensus"}
    assert valuations["pe_multiple"]["target_price"] == pytest.approx(6.5 * 25.0)
    assert data["summary"] == {
        "methods_used": 3,
        "has_dcf": True,
        "has_pe": True,
        "has_technical": True,
        "has_consensus": True,
    }


def test_valuation_tool_partial_inputs_no_consensus():
    payload = _env(
        ValuationTool()._run(ticker="MSFT", current_price=400.0, earnings_per_share=11.0, target_pe_ratio=30.0)
    )
    data = payload["data"]
    assert set(data["valuations"]) == {"pe_multiple"}
    assert data["summary"]["has_consensus"] is False
    assert data["summary"]["methods_used"] == 1


def test_valuation_tool_error_envelope_on_invalid_input():
    # current_price is required by the schema
    payload = _env(ValuationTool()._run(ticker="AAPL"))
    assert payload["success"] is False
    assert "Valuation calculation failed" in payload["error"]
    assert payload["data"] == {"ticker": "AAPL"}


def test_valuation_tool_error_envelope_unknown_ticker_key():
    payload = _env(ValuationTool()._run())
    assert payload["success"] is False
    assert payload["data"] == {"ticker": "unknown"}
