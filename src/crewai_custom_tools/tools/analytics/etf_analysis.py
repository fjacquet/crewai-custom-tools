"""ETF Analysis Tool - CrewAI tool wrapper for ETF-specific metrics.

This tool provides AI agents with access to ETF-specific calculations including
tracking error, correlation, expense impact, liquidity scoring, and concentration
risk. It wraps the pure functions in
:mod:`crewai_custom_tools.tools.analytics.etf_metrics`.

Port note: ported from finwiz's ``tools/etf_analysis_tool.py`` (226 LOC). All
inputs (returns series, holdings, expense ratio, volume, spread, market cap)
are supplied directly by the caller — the original tool never called
yfinance or any other network API itself (data collection happens upstream,
in the finwiz crew that constructs these kwargs). This tool is therefore pure
computation and is NOT wrapped with ``@api_tool`` (that decorator's
timeout/rate-limit/retry machinery targets outbound network calls, none of
which exist here). The finwiz factory function (``get_etf_analysis_tool``) is
intentionally not ported.

Usage in crews:
    from crewai_custom_tools.tools.analytics.etf_analysis import ETFAnalysisTool

    tool = ETFAnalysisTool()
    result = tool._run(
        ticker="SPY",
        etf_returns=[0.01, 0.02, -0.01],
        benchmark_returns=[0.011, 0.019, -0.009],
        expense_ratio=0.0009,
        avg_daily_volume=50000000,
    )
"""

import logging
from typing import Any

import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models.analytics_models import ETFAnalysisInput
from crewai_custom_tools.tools.analytics.etf_metrics import (
    calculate_concentration_risk,
    calculate_correlation,
    calculate_etf_efficiency_score,
    calculate_expense_impact,
    calculate_liquidity_score,
    calculate_tracking_error,
)

logger = logging.getLogger(__name__)


class ETFAnalysisTool(BaseTool):
    """
    Tool for analyzing ETF quality and characteristics.

    This tool provides AI agents with access to:
    - Tracking error vs benchmark
    - Correlation with benchmark
    - Expense ratio impact on returns
    - Liquidity scoring
    - Concentration risk from top holdings
    - Overall ETF efficiency score

    The tool returns structured results with ratings and detailed metrics
    for each analysis dimension.
    """

    name: str = "etf_analysis_tool"
    description: str = """
    Analyze ETF quality using multiple metrics and provide comprehensive assessment.

    Calculates:
    - Tracking error: How closely ETF follows benchmark
    - Correlation: Relationship with benchmark returns
    - Expense impact: Long-term cost of expense ratio
    - Liquidity score: Trading ease based on volume, spread, size
    - Concentration risk: Top holdings concentration
    - Efficiency score: Overall ETF quality rating

    Returns JSON with detailed metrics, scores, and ratings for each dimension.

    Input format:
    {
        "ticker": "SPY",
        "etf_returns": [0.01, 0.02, -0.01, 0.015],
        "benchmark_returns": [0.011, 0.019, -0.009, 0.014],
        "expense_ratio": 0.0009,
        "avg_daily_volume": 50000000,
        "bid_ask_spread_pct": 0.01,
        "market_cap": 400000000000,
        "holdings": [
            {"ticker": "AAPL", "weight": 0.07},
            {"ticker": "MSFT", "weight": 0.06}
        ]
    }
    """
    args_schema: type[BaseModel] = ETFAnalysisInput

    def _run(self, **kwargs: Any) -> str:
        """
        Execute ETF analysis.

        Args:
            **kwargs: ETF analysis parameters (see ETFAnalysisInput schema)

        Returns:
            JSON envelope string (``ok()``/``err()``) with analysis results

        """
        try:
            # Validate input
            input_data = ETFAnalysisInput(**kwargs)

            logger.info(f"Analyzing ETF {input_data.ticker}")

            results: dict[str, Any] = {"ticker": input_data.ticker, "metrics": {}, "ratings": {}}

            # Tracking error and correlation
            if input_data.etf_returns and input_data.benchmark_returns:
                etf_returns = pd.Series(input_data.etf_returns)
                benchmark_returns = pd.Series(input_data.benchmark_returns)

                tracking_error = calculate_tracking_error(etf_returns, benchmark_returns, annualize=True)
                correlation = calculate_correlation(etf_returns, benchmark_returns)

                results["metrics"]["tracking_error"] = tracking_error
                results["metrics"]["tracking_error_pct"] = tracking_error * 100
                results["metrics"]["correlation"] = correlation

                # Rating for tracking error
                if tracking_error <= 0.002:
                    te_rating = "Excellent"
                elif tracking_error <= 0.005:
                    te_rating = "Good"
                elif tracking_error <= 0.010:
                    te_rating = "Fair"
                else:
                    te_rating = "Poor"

                results["ratings"]["tracking_error"] = te_rating

                logger.debug(f"Tracking error: {tracking_error * 100:.3f}% ({te_rating})")
                logger.debug(f"Correlation: {correlation:.3f}")

            # Expense impact
            if input_data.expense_ratio is not None and input_data.etf_returns:
                returns = pd.Series(input_data.etf_returns)
                expense_impact = calculate_expense_impact(returns, input_data.expense_ratio, years=10)

                results["metrics"]["expense_impact"] = expense_impact
                results["metrics"]["expense_ratio_pct"] = input_data.expense_ratio * 100

                logger.debug(f"Expense impact: {expense_impact['annual_drag'] * 100:.2f}% annual, {expense_impact['cumulative_cost'] * 100:.1f}% over 10 years")

            # Liquidity score
            if input_data.avg_daily_volume is not None and input_data.bid_ask_spread_pct is not None and input_data.market_cap is not None:
                liquidity = calculate_liquidity_score(
                    avg_daily_volume=input_data.avg_daily_volume,
                    bid_ask_spread_pct=input_data.bid_ask_spread_pct,
                    market_cap=input_data.market_cap,
                )

                results["metrics"]["liquidity"] = liquidity
                results["ratings"]["liquidity"] = liquidity["liquidity_rating"]

                logger.debug(f"Liquidity score: {liquidity['liquidity_score']:.0f}/100 ({liquidity['liquidity_rating']})")

            # Concentration risk
            if input_data.holdings:
                concentration = calculate_concentration_risk(input_data.holdings, top_n=10)

                results["metrics"]["concentration"] = concentration
                results["ratings"]["concentration"] = concentration["concentration_rating"]

                logger.debug(f"Concentration: Top 10 = {concentration['top_n_concentration'] * 100:.1f}%, Rating = {concentration['concentration_rating']}")

            # Overall efficiency score
            if "tracking_error" in results["metrics"] and "expense_ratio_pct" in results["metrics"] and "liquidity" in results["metrics"]:
                if input_data.expense_ratio is not None:
                    efficiency = calculate_etf_efficiency_score(
                        tracking_error=results["metrics"]["tracking_error"],
                        expense_ratio=input_data.expense_ratio,
                        liquidity_score=results["metrics"]["liquidity"]["liquidity_score"],
                    )

                    results["metrics"]["efficiency"] = efficiency
                    results["ratings"]["overall_efficiency"] = efficiency["efficiency_rating"]

                    logger.info(f"ETF efficiency score: {efficiency['efficiency_score']:.0f}/100 ({efficiency['efficiency_rating']})")

            # Summary
            results["summary"] = {
                "has_tracking_analysis": "tracking_error" in results["metrics"],
                "has_expense_analysis": "expense_impact" in results["metrics"],
                "has_liquidity_analysis": "liquidity" in results["metrics"],
                "has_concentration_analysis": "concentration" in results["metrics"],
                "has_efficiency_score": "efficiency" in results["metrics"],
                "overall_rating": results["ratings"].get("overall_efficiency", "Not calculated"),
            }

            return ok(results)

        except Exception as e:
            error_msg = f"ETF analysis failed: {e!s}"
            logger.error(error_msg, exc_info=True)
            return err(error_msg, data={"ticker": kwargs.get("ticker", "unknown")})
