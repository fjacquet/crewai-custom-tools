"""
A+ Investment Scoring Tool for proactive discovery of exceptional investment
opportunities.

This tool implements comprehensive A+ scoring for ETFs, stocks, and
cryptocurrencies using dynamic criteria that adapt to market conditions.

Port note: ported from finwiz's ``tools/a_plus_scoring_tool.py`` (164 LOC),
with the scoring logic split across ``scoring_algorithms.py``/
``scoring_criteria.py`` (ported from finwiz's ``tools/scoring/``) and grading
from ``grading.py`` (ported from finwiz's
``scoring/grading_system.py::score_to_grade`` only — see that module's
docstring).

Behavioral change #1 — envelope: ``_run`` returns the canonical
``ok()``/``err()`` JSON envelope (finwiz's returned a raw ``dict``). This
tool has a programmatic caller — ``ScreeningRanking.score_candidates`` in
``screening_ranking.py`` — which is adapted to parse the envelope with
``parse_tool_result``.

Behavioral change #2 — composite_score bug fix (Wave 3 Task 4): finwiz's raw
dict put the composite score ONLY under ``analysis_summary.composite_score``.
Its programmatic caller (``screening_ranking.score_candidates``'s detailed
path) read ``score_result.get("composite_score", 0.5)`` at the TOP level — a
key that never existed there — so every detailed-analysis screening call
silently scored 0.5 regardless of the real result (see
``analytics/screening_ranking.py`` for the caller-side half of this fix).
Fixed here by ALSO emitting ``composite_score`` at the top level of the
envelope's ``data`` payload (kept in ``analysis_summary`` too, unchanged, for
shape stability with anything reading that nested path). One value, two
places it's reachable from — no divergence risk since both are written from
the same local variable in the same statement.
"""

import logging
from datetime import datetime
from typing import Any, Literal

from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models.analytics_models import APlusScore, APlusScoringInput
from crewai_custom_tools.tools.analytics.grading import score_to_grade
from crewai_custom_tools.tools.analytics.scoring_algorithms import (
    calculate_fundamental_score,
    calculate_quality_score,
    calculate_risk_score,
    calculate_technical_score,
    get_scoring_weights,
)
from crewai_custom_tools.tools.analytics.scoring_criteria import (
    analyze_strengths_weaknesses,
    assess_market_regime,
    calculate_confidence_level,
    generate_a_plus_rationale,
    get_dynamic_criteria,
)

logger = logging.getLogger(__name__)


class APlusScoringTool(BaseTool):
    """
    A+ Investment Scoring Tool for discovering exceptional investment opportunities.

    This tool provides comprehensive A+ scoring for ETFs, stocks, and cryptocurrencies
    using dynamic criteria that adapt to market conditions. It integrates with the
    existing FinWiz-style grading system to identify investments with A+ potential.

    Key Features:
    - Dynamic criteria adjustment based on market regime
    - Comprehensive scoring across multiple dimensions
    - Integration with existing grading system
    - Detailed rationale and confidence assessment
    """

    name: str = "A+ Investment Scoring Tool"
    description: str = (
        "Comprehensive A+ scoring tool that evaluates ETFs, stocks, and cryptocurrencies "
        "using dynamic criteria adapted to current market conditions. Identifies investments "
        "with A+ potential (score ≥ 0.95) through multi-dimensional analysis."
    )
    args_schema: type[BaseModel] = APlusScoringInput

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the A+ Scoring Tool with caching capabilities."""
        super().__init__(**kwargs)
        self._regime_cache: dict[str, Any] = {}

    def _run(
        self,
        symbol: str,
        asset_type: Literal["etf", "stock", "crypto"],
        fundamental_data: dict[str, Any] | None = None,
        market_context: dict[str, Any] | None = None,
        custom_criteria: dict[str, float] | None = None,
    ) -> str:
        """Execute A+ scoring analysis.

        Returns:
            JSON envelope string (``ok()``/``err()``) with the scoring results.

        """
        try:
            # Normalize inputs
            symbol = symbol.upper().strip()
            fundamental_data = fundamental_data or {}
            market_context = market_context or {}
            custom_criteria = custom_criteria or {}

            # Get current market regime
            market_regime = assess_market_regime(market_context, self._regime_cache)

            # Get dynamic scoring criteria
            scoring_criteria = get_dynamic_criteria(market_regime, custom_criteria)

            # Calculate component scores
            fundamental_score = calculate_fundamental_score(symbol, asset_type, fundamental_data, scoring_criteria)
            technical_score = calculate_technical_score(symbol, asset_type, fundamental_data, market_regime)
            quality_score = calculate_quality_score(symbol, asset_type, fundamental_data, scoring_criteria)
            risk_score = calculate_risk_score(symbol, asset_type, fundamental_data, market_regime)

            # Calculate composite score with weights
            weights = get_scoring_weights(asset_type, market_regime)
            composite_score = (
                fundamental_score * weights["fundamental"]
                + technical_score * weights["technical"]
                + quality_score * weights["quality"]
                + risk_score * weights["risk"]
            )

            # Generate grade info
            grade_info = score_to_grade(composite_score)

            # Analyze strengths and weaknesses
            strengths, weaknesses = analyze_strengths_weaknesses(
                symbol,
                asset_type,
                fundamental_data,
                {
                    "fundamental": fundamental_score,
                    "technical": technical_score,
                    "quality": quality_score,
                    "risk": risk_score,
                },
            )

            # Generate A+ rationale
            a_plus_rationale = generate_a_plus_rationale(
                symbol, asset_type, composite_score, strengths, weaknesses, market_regime
            )

            # Calculate confidence level
            confidence_level = calculate_confidence_level(fundamental_data, market_regime, composite_score)

            # Create A+ score object
            a_plus_score = APlusScore(
                symbol=symbol,
                asset_type=asset_type,
                composite_score=composite_score,
                grade_info=grade_info,
                fundamental_score=fundamental_score,
                technical_score=technical_score,
                quality_score=quality_score,
                risk_score=risk_score,
                strengths=strengths,
                weaknesses=weaknesses,
                a_plus_rationale=a_plus_rationale,
                confidence_level=confidence_level,
                market_regime=market_regime,
                scoring_criteria=scoring_criteria,
                analysis_timestamp=datetime.now(),
            )

            return ok(
                {
                    "symbol": symbol,
                    "asset_type": asset_type,
                    # Top-level composite_score — bug-fix companion to the copy
                    # nested under analysis_summary below. See module docstring.
                    "composite_score": composite_score,
                    "a_plus_score": a_plus_score.model_dump(),
                    "is_a_plus_candidate": composite_score >= 0.95,
                    "grade": grade_info.grade,
                    "percentage": grade_info.percentage,
                    "recommendation": grade_info.action,
                    "analysis_summary": {
                        "composite_score": composite_score,
                        "component_scores": {
                            "fundamental": fundamental_score,
                            "technical": technical_score,
                            "quality": quality_score,
                            "risk": risk_score,
                        },
                        "top_strengths": strengths[:3],
                        "main_concerns": weaknesses[:2],
                        "confidence": confidence_level,
                    },
                }
            )

        except Exception as e:
            error_msg = f"A+ scoring failed for {symbol}: {e!s}"
            logger.error(error_msg)
            return err(
                error_msg,
                data={
                    "symbol": symbol,
                    "asset_type": asset_type,
                    "composite_score": 0.0,
                    "is_a_plus_candidate": False,
                },
            )
