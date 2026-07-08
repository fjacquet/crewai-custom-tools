"""Transparent 0-10 risk score for a ticker from real Yahoo Finance signals.

Built fresh (the finwiz original was coupled to an app-specific scoring subsystem).
Every sub-score, weight, and contribution is returned so the methodology is auditable —
no hidden magic numbers, no fabricated inputs.
"""

import math
from typing import Optional

import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

# Factor weights (sum to 1.0). Score is renormalized by the weight of available factors.
_WEIGHTS = {"beta": 0.30, "debt_to_equity": 0.25, "volatility": 0.30, "size": 0.15}


class RiskScoringInput(BaseModel):
    """Input schema for StandardizedRiskScoringTool."""

    ticker: str = Field(..., description="The stock/ETF ticker to score (e.g. 'AAPL').")


def _clamp(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 2)


def _score_beta(beta: Optional[float]) -> Optional[float]:
    """beta 0 -> 0, beta 2.0+ -> 10."""
    return None if beta is None else _clamp(beta * 5.0)


def _score_debt_to_equity(dte: Optional[float]) -> Optional[float]:
    """yfinance debtToEquity is a percent (150 == 1.5x): 0 -> 0, 300%+ -> 10."""
    return None if dte is None else _clamp(dte / 30.0)


def _score_volatility(vol: Optional[float]) -> Optional[float]:
    """Annualized stdev of daily returns: 0 -> 0, 60%+ -> 10."""
    return None if vol is None else _clamp(vol / 0.06)


def _score_size(market_cap: Optional[float]) -> Optional[float]:
    """Smaller cap = higher risk: >=200B -> 0, <=300M -> 10 (log-scaled)."""
    if not market_cap or market_cap <= 0:
        return None
    lo, hi = math.log10(3e8), math.log10(2e11)
    x = max(lo, min(hi, math.log10(market_cap)))
    return _clamp((hi - x) / (hi - lo) * 10.0)


_SCORERS = {
    "beta": _score_beta,
    "debt_to_equity": _score_debt_to_equity,
    "volatility": _score_volatility,
    "size": _score_size,
}


def _annualized_volatility(ticker_obj) -> Optional[float]:
    """Annualized volatility from 1y of daily closes, or None if unavailable."""
    try:
        hist = ticker_obj.history(period="1y")
    except Exception:  # noqa: BLE001
        return None
    if hist is None or hist.empty or "Close" not in hist:
        return None
    returns = hist["Close"].pct_change().dropna()
    if len(returns) < 2:
        return None
    return float(returns.std() * math.sqrt(252))


class StandardizedRiskScoringTool(BaseTool):
    """Compute a transparent 0-10 risk score for a ticker from live market signals."""

    name: str = "risk_scoring"
    description: str = (
        "Compute a transparent 0-10 risk score (0 = low, 10 = high) for a stock/ETF from "
        "real Yahoo Finance signals — beta, debt/equity, annualized volatility, and market-cap "
        "size — returning the per-factor breakdown so the methodology is auditable."
    )
    args_schema: type[BaseModel] = RiskScoringInput

    @api_tool(provider="YahooFinance", endpoint="RiskScore")
    def _run(self, ticker: str) -> str:
        obj = yf.Ticker(ticker)
        info = obj.info or {}
        raw = {
            "beta": info.get("beta"),
            "debt_to_equity": info.get("debtToEquity"),
            "volatility": _annualized_volatility(obj),
            "size": info.get("marketCap"),
        }

        factors: dict = {}
        available_weight = 0.0
        weighted_sum = 0.0
        for name, weight in _WEIGHTS.items():
            sub = _SCORERS[name](raw[name])
            if sub is None:
                factors[name] = {"value": raw[name], "weight": weight, "available": False}
                continue
            factors[name] = {
                "value": raw[name],
                "sub_score": sub,
                "weight": weight,
                "contribution": round(sub * weight, 3),
                "available": True,
            }
            available_weight += weight
            weighted_sum += sub * weight

        if available_weight == 0:
            return err(f"No risk factors available for ticker {ticker!r}")

        risk_score = round(weighted_sum / available_weight, 2)
        return ok(
            {
                "ticker": ticker.upper(),
                "risk_score": risk_score,
                "scale": "0 (low) - 10 (high)",
                "factors": factors,
                "note": (
                    "risk_score = weighted mean of available factor sub-scores, "
                    "renormalized by the total weight of available factors."
                ),
            }
        )
