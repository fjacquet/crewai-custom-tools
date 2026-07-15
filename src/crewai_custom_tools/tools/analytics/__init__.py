"""Valuation, ETF, regulatory compliance, and portfolio-sizing analytics
tools.

Ported from finwiz's ``tools/valuation_tool.py`` + ``quantitative/price_targets.py``,
``tools/etf_analysis_tool.py`` + ``quantitative/etf/etf_metrics.py``,
``tools/regulatory_compliance_tool.py``, ``tools/position_sizing_tool.py``,
and ``tools/price_target_calculator.py``. All are pure computation over
caller-supplied inputs — none call yfinance or any other network API — so
none carry the ``@api_tool`` decorator used by network-backed tools
elsewhere in this package.

``RegulatoryComplianceTool`` is a CrewAI ``BaseTool`` (agent-facing, returns
the ``ok()``/``err()`` envelope). ``PositionSizingTool`` and
``PriceTargetCalculator`` are plain classes with programmatic callers in
finwiz (its rebalancing crew) — they return typed pydantic models directly,
not the envelope.
"""

from crewai_custom_tools.tools.analytics.etf_analysis import ETFAnalysisTool
from crewai_custom_tools.tools.analytics.position_sizing import (
    HoldingSizingProfile,
    PortfolioContext,
    PositionSizingTool,
)
from crewai_custom_tools.tools.analytics.price_target_calculator import (
    FundamentalData,
    PriceHistory,
    PriceTargetCalculator,
)
from crewai_custom_tools.tools.analytics.regulatory_compliance import RegulatoryComplianceTool
from crewai_custom_tools.tools.analytics.valuation import ValuationTool

__all__ = [
    "ValuationTool",
    "ETFAnalysisTool",
    "RegulatoryComplianceTool",
    "PositionSizingTool",
    "PortfolioContext",
    "HoldingSizingProfile",
    "PriceTargetCalculator",
    "PriceHistory",
    "FundamentalData",
]
