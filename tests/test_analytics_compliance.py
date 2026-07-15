"""Tests for the regulatory compliance analytics tool.

The tool is pure computation over hardcoded classification/compliance/risk
tables (no network), so tests run offline with direct inputs — nothing to
mock. There is no finwiz test file to port from (none existed upstream);
these tests are written fresh, following the envelope-testing pattern used
by test_analytics_valuation.py / test_analytics_etf.py.
"""

import json

from crewai_custom_tools.tools.analytics.regulatory_compliance import RegulatoryComplianceTool


def _env(result):
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --------------------------------------------------------------------------- #
# Happy path: known symbol, default jurisdictions
# --------------------------------------------------------------------------- #
def test_btc_defaults_to_all_five_jurisdictions_and_is_compliant():
    payload = _env(RegulatoryComplianceTool()._run(symbol="btc"))
    assert payload["success"] is True
    assert payload["error"] is None

    data = payload["data"]
    assert data["symbol"] == "BTC"
    assert data["jurisdictions_analyzed"] == ["US", "EU", "Switzerland", "UK", "Singapore"]

    classification = data["crypto_classification"]
    assert classification["primary_classification"] == "commodity"
    assert classification["regulatory_clarity"] == "high"

    compliance = data["compliance_status"]
    assert set(compliance) == {"US", "EU", "Switzerland", "UK", "Singapore"}
    assert compliance["US"]["status"] == "compliant"
    assert compliance["US"]["regulatory_framework"] == "CFTC commodity regulation"

    risk = data["regulatory_risk"]
    assert risk["symbol"] == "BTC"
    assert 0.0 <= risk["risk_score"] <= 5.0
    assert risk["risk_level"] in {"Low", "Medium", "High", "Very High"}

    summary = data["regulatory_summary"]
    # 3/5 jurisdictions compliant (US, Switzerland, Singapore) -> "mixed"
    # (EU is "transitioning" and UK is "evolving", neither counts as compliant).
    assert summary["overall_status"] == "mixed"
    assert summary["compliant_jurisdictions"] == 3
    assert summary["total_jurisdictions"] == 5
    assert summary["investment_suitability"] in {"suitable", "moderate", "high_risk"}
    assert len(summary["key_risks"]) <= 3


# --------------------------------------------------------------------------- #
# Governance token: low clarity, higher risk, DeFi-specific risk factor
# --------------------------------------------------------------------------- #
def test_uni_governance_token_gets_low_clarity_and_defi_risk_factor():
    payload = _env(RegulatoryComplianceTool()._run(symbol="UNI", jurisdictions=["US"]))
    data = payload["data"]

    assert data["crypto_classification"]["primary_classification"] == "governance_token"
    assert data["crypto_classification"]["regulatory_clarity"] == "low"

    risk_factors = data["regulatory_risk"]["risk_factors"]
    assert any("DeFi governance tokens" in f for f in risk_factors)
    assert any("Governance tokens face higher securities regulation risk" in f for f in risk_factors)

    recommendations = data["regulatory_summary"]["recommendations"]
    assert any("DeFi governance tokens face elevated regulatory scrutiny" in r for r in recommendations)


# --------------------------------------------------------------------------- #
# Unknown symbol falls back to the low-clarity default classification
# --------------------------------------------------------------------------- #
def test_unknown_symbol_defaults_to_low_clarity_utility_token():
    payload = _env(RegulatoryComplianceTool()._run(symbol="ZZZZ", jurisdictions=["US", "EU"]))
    data = payload["data"]

    classification = data["crypto_classification"]
    assert classification["primary_classification"] == "utility_token"
    assert classification["sec_classification"] == "unclear"
    assert classification["regulatory_clarity"] == "low"
    assert classification["symbol"] == "ZZZZ"


# --------------------------------------------------------------------------- #
# Optional sections can be disabled
# --------------------------------------------------------------------------- #
def test_can_disable_compliance_status_and_risk_assessment_sections():
    payload = _env(
        RegulatoryComplianceTool()._run(
            symbol="ETH",
            include_risk_assessment=False,
            include_compliance_status=False,
        )
    )
    data = payload["data"]
    assert "compliance_status" not in data
    assert "regulatory_risk" not in data
    # Summary still generated, just with empty upstream sections
    assert "regulatory_summary" in data
    assert data["regulatory_summary"]["total_jurisdictions"] == 0


# --------------------------------------------------------------------------- #
# Jurisdiction not covered by the hardcoded frameworks falls back to unknown
# --------------------------------------------------------------------------- #
def test_uncovered_jurisdiction_returns_unknown_status():
    payload = _env(RegulatoryComplianceTool()._run(symbol="BTC", jurisdictions=["Narnia"]))
    data = payload["data"]
    assert data["compliance_status"]["Narnia"]["status"] == "unknown"
    assert data["compliance_status"]["Narnia"]["regulatory_clarity"] == "low"


# --------------------------------------------------------------------------- #
# Error envelope on invalid input
# --------------------------------------------------------------------------- #
def test_error_envelope_when_symbol_missing():
    payload = _env(RegulatoryComplianceTool()._run(symbol=None))
    assert payload["success"] is False
    assert "Regulatory compliance analysis failed" in payload["error"]
