"""
Ranking algorithms for A+ market screening candidates.

This module contains scoring and ranking algorithms used to evaluate
and rank investment candidates during A+ market screening operations.

Port note: ported from finwiz's ``tools/screening_ranking.py`` (242 LOC).
``ScreeningCandidate`` stays local to this module rather than moving to
``models/analytics_models.py`` — matching this package's precedent of
colocating a tool's Pydantic models with its own module (see
``PortfolioContext``/``HoldingSizingProfile`` in ``position_sizing.py``,
``PriceHistory``/``FundamentalData`` in ``price_target_calculator.py``);
``models/analytics_models.py`` only carries the Pydantic classes the porting
brief names explicitly, which doesn't include ``ScreeningCandidate``.

Minor cleanup from finwiz: the ``ScreeningUtils`` import (used only for
``generate_screening_rationale``/``extract_key_metrics``) is now a top-level
import instead of finwiz's inline import inside ``score_candidates`` — there
is no circular-import reason for it to be local (``screening_utils.py``
never imports this module), so hoisting it is a pure readability cleanup
with no behavior change.

Bug fix — composite_score fallback (Wave 3 Task 4): ``ScreeningRanking``'s
detailed-analysis path calls ``APlusScoringTool._run(...)`` programmatically.
finwiz's version read ``score_result.get("composite_score", 0.5)`` straight
off the scorer's raw dict — but the scorer only ever nested that value
under ``analysis_summary.composite_score``, never at the top level. Every
detailed-analysis screening call therefore silently scored 0.5 regardless of
the real result (verified findable in finwiz by tracing ``score_to_grade``
usage — the composite score the grade was computed from never made it back
out to this top-level key). Fixed on both ends of the seam:
- ``APlusScoringTool`` (``a_plus_scoring.py``) now ALSO emits
  ``composite_score`` at the top level of its envelope ``data`` (in addition
  to the existing nested copy).
- This module parses that envelope with ``parse_tool_result`` and reads
  ``composite_score`` from the top level — now a genuine fallback for actual
  parse/failure cases, not a guaranteed miss. See
  ``tests/test_analytics_aplus_screening.py`` for the regression test that
  pins a known, non-0.5 composite score through this path.
"""

from datetime import datetime
import logging
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from crewai_custom_tools.core.results import ToolResultError, parse_tool_result
from crewai_custom_tools.tools.analytics.a_plus_scoring import APlusScoringTool
from crewai_custom_tools.tools.analytics.screening_utils import ScreeningUtils

logger = logging.getLogger(__name__)


class ScreeningCandidate(BaseModel):
    """A candidate investment from screening."""

    symbol: str
    name: str
    asset_type: Literal["etf", "stock", "crypto"]
    preliminary_score: float = Field(ge=0.0, le=1.0)
    meets_a_plus_criteria: bool
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    screening_rationale: str
    data_source: str
    screened_at: datetime


class ScreeningRanking:
    """Ranking algorithms for screening candidates."""

    def __init__(self) -> None:
        """Initialize screening ranking."""
        self._a_plus_scorer = APlusScoringTool()
        self._utils = ScreeningUtils()

    def score_candidates(self, candidates: list[dict[str, Any]], asset_type: str, min_score: float, detailed_analysis: bool) -> list[ScreeningCandidate]:
        """Score filtered candidates using A+ scoring."""
        scored_candidates = []

        for candidate in candidates:
            try:
                symbol = candidate["symbol"]
                market_data = candidate["market_data"]

                # Calculate preliminary score
                if detailed_analysis:
                    # Use full A+ scoring tool
                    raw_result = self._a_plus_scorer._run(
                        symbol=symbol,
                        asset_type=cast(Literal["etf", "stock", "crypto"], asset_type),
                        fundamental_data=market_data,
                        market_context={},
                    )
                    try:
                        score_data = parse_tool_result(raw_result)
                        preliminary_score = score_data.get("composite_score", 0.5)
                    except ToolResultError as parse_error:
                        logger.warning(f"A+ scorer envelope failed for {symbol}: {parse_error}")
                        preliminary_score = 0.5
                else:
                    # Use simplified scoring for efficiency
                    preliminary_score = self.calculate_preliminary_score(market_data, asset_type)

                # Determine if meets A+ criteria
                meets_a_plus = preliminary_score >= min_score

                # Generate screening rationale
                rationale = self._utils.generate_screening_rationale(market_data, asset_type, preliminary_score, meets_a_plus)

                # Extract key metrics
                key_metrics = self._utils.extract_key_metrics(market_data, asset_type)

                # Create candidate object
                screening_candidate = ScreeningCandidate(
                    symbol=symbol,
                    name=market_data.get("name", symbol),
                    asset_type=cast(Literal["etf", "stock", "crypto"], asset_type),
                    preliminary_score=preliminary_score,
                    meets_a_plus_criteria=meets_a_plus,
                    key_metrics=key_metrics,
                    screening_rationale=rationale,
                    data_source=market_data.get("source", "Market Data"),
                    screened_at=datetime.now(),
                )

                scored_candidates.append(screening_candidate)

            except (KeyError, TypeError, ValueError, AttributeError) as e:
                # Skip candidates that fail scoring
                logger.warning(f"Failed to score candidate {candidate.get('symbol', 'unknown')}: {e}")
                continue

        return scored_candidates

    def calculate_preliminary_score(self, market_data: dict[str, Any], asset_type: str) -> float:
        """Calculate simplified preliminary score for efficiency."""
        try:
            if asset_type == "etf":
                return self._score_etf_preliminary(market_data)
            elif asset_type == "stock":
                return self._score_stock_preliminary(market_data)
            elif asset_type == "crypto":
                return self._score_crypto_preliminary(market_data)
            else:
                return 0.5

        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Failed to calculate preliminary score for {asset_type}: {e}")
            return 0.5

    def _score_etf_preliminary(self, data: dict[str, Any]) -> float:
        """Calculate preliminary ETF score."""
        score = 0.0

        # Expense ratio (40% weight)
        expense_ratio = data.get("expense_ratio", 0.5)
        if expense_ratio <= 0.05:
            score += 0.4
        elif expense_ratio <= 0.15:
            score += 0.3
        elif expense_ratio <= 0.25:
            score += 0.2

        # AUM (30% weight)
        aum = data.get("aum", 0)
        if aum >= 10e9:
            score += 0.3
        elif aum >= 1e9:
            score += 0.2
        elif aum >= 500e6:
            score += 0.1

        # Tracking error (20% weight)
        tracking_error = data.get("tracking_error", 0.01)
        if tracking_error <= 0.001:
            score += 0.2
        elif tracking_error <= 0.002:
            score += 0.15
        elif tracking_error <= 0.005:
            score += 0.1

        # History (10% weight)
        history_years = data.get("history_years", 0)
        if history_years >= 10:
            score += 0.1
        elif history_years >= 5:
            score += 0.075
        elif history_years >= 3:
            score += 0.05

        return min(score, 1.0)

    def _score_stock_preliminary(self, data: dict[str, Any]) -> float:
        """Calculate preliminary stock score."""
        score = 0.0

        # ROE (30% weight)
        roe = data.get("roe", 0.1)
        if roe >= 0.25:
            score += 0.3
        elif roe >= 0.20:
            score += 0.25
        elif roe >= 0.15:
            score += 0.15

        # Revenue growth (25% weight)
        revenue_growth = data.get("revenue_growth", 0.05)
        if revenue_growth >= 0.20:
            score += 0.25
        elif revenue_growth >= 0.15:
            score += 0.2
        elif revenue_growth >= 0.10:
            score += 0.15

        # Debt management (20% weight)
        debt_to_equity = data.get("debt_to_equity", 0.5)
        if debt_to_equity <= 0.2:
            score += 0.2
        elif debt_to_equity <= 0.3:
            score += 0.15
        elif debt_to_equity <= 0.5:
            score += 0.1

        # Market cap (15% weight)
        market_cap = data.get("market_cap", 0)
        if market_cap >= 100e9:
            score += 0.15
        elif market_cap >= 10e9:
            score += 0.12
        elif market_cap >= 1e9:
            score += 0.08

        # Free cash flow (10% weight)
        if data.get("fcf_positive", False) and data.get("fcf_growing", False):
            score += 0.1
        elif data.get("fcf_positive", False):
            score += 0.05

        return min(score, 1.0)

    def _score_crypto_preliminary(self, data: dict[str, Any]) -> float:
        """Calculate preliminary crypto score."""
        score = 0.0

        # Market cap (35% weight)
        market_cap = data.get("market_cap", 0)
        if market_cap >= 100e9:
            score += 0.35
        elif market_cap >= 50e9:
            score += 0.3
        elif market_cap >= 10e9:
            score += 0.2

        # Daily volume (25% weight)
        daily_volume = data.get("daily_volume", 0)
        if daily_volume >= 2e9:
            score += 0.25
        elif daily_volume >= 1e9:
            score += 0.2
        elif daily_volume >= 500e6:
            score += 0.15

        # Age/Maturity (20% weight)
        age_months = data.get("age_months", 0)
        if age_months >= 60:
            score += 0.2
        elif age_months >= 36:
            score += 0.15
        elif age_months >= 24:
            score += 0.1

        # Institutional adoption (10% weight)
        if data.get("institutional_adoption", False):
            score += 0.1

        # Real utility (10% weight)
        if data.get("real_utility", False):
            score += 0.1

        return min(score, 1.0)
