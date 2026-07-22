"""Valuation, ETF, regulatory compliance, portfolio-sizing, and A+ grading/
screening analytics tools.

Ported from finwiz's ``tools/valuation_tool.py`` + ``quantitative/price_targets.py``,
``tools/etf_analysis_tool.py`` + ``quantitative/etf/etf_metrics.py``,
``tools/regulatory_compliance_tool.py``, ``tools/position_sizing_tool.py``,
``tools/price_target_calculator.py``, and the A+ grading cluster
(``tools/scoring/``, ``scoring/grading_system.py::score_to_grade``,
``tools/a_plus_scoring_tool.py``, ``tools/screening_criteria.py``,
``tools/screening_utils.py``, ``tools/screening_ranking.py``,
``tools/market_screening_tool.py``). All are pure computation over
caller-supplied or static-lookup-table data — none call yfinance or any
other network API — so none carry the ``@api_tool`` decorator used by
network-backed tools elsewhere in this package.

``RegulatoryComplianceTool``, ``APlusScoringTool``, and
``APlusScreeningTool`` are CrewAI ``BaseTool``\\ s (agent-facing, return the
``ok()``/``err()`` envelope). ``PositionSizingTool`` and
``PriceTargetCalculator`` are plain classes with programmatic callers in
finwiz (its rebalancing crew) — they return typed pydantic models directly,
not the envelope. ``APlusScreeningTool`` is finwiz's ``MarketScreeningTool``
RENAMED (tool name ``"aplus_screening"``) to avoid colliding with this
package's own, simpler ``tools/finance/screening.py::MarketScreeningTool``
(tool name ``"market_screening"``).
"""

from crewai_custom_tools.tools.analytics.a_plus_scoring import APlusScoringTool
from crewai_custom_tools.tools.analytics.aplus_screening import APlusScreeningTool
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
from crewai_custom_tools.tools.analytics.screening_ranking import ScreeningCandidate, ScreeningRanking
from crewai_custom_tools.tools.analytics.valuation import ValuationTool

__all__ = [
    "APlusScoringTool",
    "APlusScreeningTool",
    "ETFAnalysisTool",
    "FundamentalData",
    "HoldingSizingProfile",
    "PortfolioContext",
    "PositionSizingTool",
    "PriceHistory",
    "PriceTargetCalculator",
    "RegulatoryComplianceTool",
    "ScreeningCandidate",
    "ScreeningRanking",
    "ValuationTool",
]
