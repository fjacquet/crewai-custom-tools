"""Pydantic models for the analytics tools (valuation, ETF metrics, regulatory
compliance, position sizing, price targets, A+ grading/screening).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ValuationInput(BaseModel):
    """Input schema for valuation calculations."""

    ticker: str = Field(..., description="Stock ticker symbol")
    current_price: float = Field(..., description="Current market price")

    # DCF inputs (optional)
    cash_flows: list[float] | None = Field(None, description="Projected annual free cash flows")
    discount_rate: float | None = Field(None, description="Discount rate (WACC) as decimal")
    terminal_growth: float | None = Field(None, description="Terminal growth rate as decimal")
    shares_outstanding: float | None = Field(None, description="Number of shares outstanding")

    # P/E inputs (optional)
    earnings_per_share: float | None = Field(None, description="Earnings per share")
    target_pe_ratio: float | None = Field(None, description="Target P/E multiple")
    sector_avg_pe: float | None = Field(None, description="Sector average P/E")

    # Technical inputs (optional)
    price_history: list[float] | None = Field(None, description="Historical prices for technical analysis")


class ETFAnalysisInput(BaseModel):
    """Input schema for ETF analysis."""

    ticker: str = Field(..., description="ETF ticker symbol")

    # Returns data (optional)
    etf_returns: list[float] | None = Field(None, description="ETF return series")
    benchmark_returns: list[float] | None = Field(None, description="Benchmark return series")

    # ETF characteristics (optional)
    expense_ratio: float | None = Field(None, description="Annual expense ratio as decimal")
    avg_daily_volume: float | None = Field(None, description="Average daily trading volume")
    bid_ask_spread_pct: float | None = Field(None, description="Bid-ask spread as percentage")
    market_cap: float | None = Field(None, description="Market capitalization")

    # Holdings data (optional)
    holdings: list[dict[str, float]] | None = Field(None, description="List of holdings with 'weight' key (as decimal)")


class RegulatoryComplianceInput(BaseModel):
    """Input schema for the Regulatory Compliance Tool.

    Port note: ported verbatim from finwiz's
    ``schemas/tools/inputs.py::RegulatoryComplianceInput``.
    """

    symbol: str = Field(..., description="The crypto symbol, e.g., BTC, ETH")
    jurisdictions: list[str] = Field(
        default=["US", "EU", "Switzerland", "UK", "Singapore"],
        description="List of jurisdictions to analyze",
    )
    include_risk_assessment: bool = Field(default=True, description="Include regulatory risk assessment")
    include_compliance_status: bool = Field(default=True, description="Include compliance status analysis")


# Asset class shared by position sizing and price target calculations.
#
# Port note: ported from finwiz's ``schemas/portfolio_review.py::AssetClass``.
AssetClass = Literal["stock", "etf", "crypto"]


class PositionSizeRecommendation(BaseModel):
    """Position sizing recommendation.

    Port note: ported verbatim from finwiz's
    ``schemas/portfolio_review.py::PositionSizeRecommendation``. finwiz's
    rebalancing crew consumes this model programmatically
    (``PositionSizingTool.calculate_position_size`` returns it) — field names,
    types, constraints, and ``model_config`` must stay identical.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    current_size_pct: float = Field(ge=0.0, le=100.0)
    recommended_size_pct: float = Field(ge=0.0, le=100.0)
    sizing_action: Literal["add", "trim", "hold", "exit"]

    # Rationale
    sizing_rationale: str
    risk_contribution: float = Field(ge=0.0, le=100.0, default=0.0)
    correlation_with_portfolio: float = Field(ge=-1.0, le=1.0, default=0.0)

    # Constraints applied
    concentration_limits_applied: bool = False
    risk_limits_applied: bool = False


class PriceTargets(BaseModel):
    """Price targets for buy/sell decisions.

    Port note: ported verbatim from finwiz's
    ``schemas/portfolio_review.py::PriceTargets``. finwiz's rebalancing crew
    consumes this model programmatically
    (``PriceTargetCalculator.calculate_targets`` returns it) — field names,
    types, constraints, and ``model_config`` must stay identical.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    current_price: float
    currency: str
    fair_value_estimate: float | None = None

    # Buy targets
    buy_target_primary: float | None = None
    buy_target_secondary: float | None = None
    buy_rationale: str = ""

    # Sell targets
    sell_target_primary: float | None = None
    sell_target_secondary: float | None = None
    stop_loss_level: float | None = None
    sell_rationale: str = ""

    # Technical levels
    support_levels: list[float] = Field(default_factory=list)
    resistance_levels: list[float] = Field(default_factory=list)

    # Metadata
    calculation_method: str = ""
    confidence_level: float = Field(ge=0.0, le=1.0, default=0.5)
    data_as_of: datetime
    data_sources: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# A+ grading cluster (Wave 3 Task 4)
#
# Port note: ported verbatim from finwiz's ``schemas/tools/inputs.py``
# (``MarketScreeningInput``, ``MarketScreeningResult``, ``APlusScoringInput``,
# ``MarketRegime``, ``ScoringCriteria``, ``APlusScore``). Two renames per the
# porting brief, to avoid colliding with this package's existing, simpler
# ``tools/finance/screening.py::MarketScreeningTool``/``MarketScreeningInput``
# (live-yfinance ticker screener):
#   - finwiz's ``MarketScreeningInput`` -> ``APlusScreeningInput``
#   - finwiz's ``MarketScreeningTool``  -> ``APlusScreeningTool`` (tools/analytics/aplus_screening.py)
# ``MarketScreeningResult`` keeps its name (no collision — finance/screening.py
# has no result model, it returns a plain envelope dict).
# --------------------------------------------------------------------------- #


class APlusScreeningInput(BaseModel):
    """Input schema for the A+ Screening Tool.

    Port note: renamed from finwiz's ``MarketScreeningInput`` (see module
    section header above).
    """

    asset_type: Literal["etf", "stock", "crypto"] = Field(..., description="Type of assets to screen")
    screening_criteria: dict[str, Any] = Field(default_factory=dict, description="Custom screening criteria (overrides defaults)")
    market_region: str = Field(default="global", description="Market region to screen (global, us, eu, etc.)")
    max_candidates: int = Field(default=50, ge=1, le=500, description="Maximum number of candidates to return")
    min_a_plus_score: float = Field(default=0.85, ge=0.0, le=1.0, description="Minimum A+ score threshold")
    include_detailed_analysis: bool = Field(default=False, description="Whether to include detailed A+ analysis for each candidate")


class MarketScreeningResult(BaseModel):
    """Result from an A+ market screening operation.

    Port note: ported from finwiz's ``MarketScreeningResult``, which was
    missing ``screening_timestamp``/``data_sources`` fields even though
    ``market_screening_tool.py`` always constructed it with both (silently
    dropped under Pydantic's default ``extra="ignore"``). Both fields are
    declared here so the port doesn't reproduce that data loss.
    """

    asset_type: Literal["etf", "stock", "crypto"]
    screening_criteria: dict[str, Any]
    market_region: str
    total_screened: int
    candidates_found: int
    a_plus_candidates: int
    candidates: list[Any]  # ScreeningCandidate at runtime (tools/analytics/screening_ranking.py)
    screening_timestamp: Any = None  # datetime
    data_sources: list[str] = Field(default_factory=list)


class APlusScoringInput(BaseModel):
    """Input schema for the A+ Investment Scoring Tool.

    Port note: ported verbatim from finwiz's ``schemas/tools/inputs.py::APlusScoringInput``.
    """

    symbol: str = Field(..., description="Investment symbol (e.g., AAPL, SPY, BTC-USD)")
    asset_type: Literal["etf", "stock", "crypto"] = Field(..., description="Type of asset to score")
    fundamental_data: dict[str, Any] = Field(default_factory=dict, description="Fundamental data for the investment")
    market_context: dict[str, Any] = Field(default_factory=dict, description="Current market context and conditions")
    custom_criteria: dict[str, float] = Field(default_factory=dict, description="Custom scoring criteria weights")


class MarketRegime(BaseModel):
    """Current market regime assessment.

    Port note: ported verbatim from finwiz's ``schemas/tools/inputs.py::MarketRegime``.
    """

    regime_type: Literal["bull", "bear", "sideways", "volatile"] = "sideways"
    vix_level: float = Field(default=20.0, ge=0.0, le=100.0)
    inflation_rate: float = Field(default=3.0, ge=-5.0, le=20.0)
    interest_rate_trend: Literal["rising", "falling", "stable"] = "stable"
    market_stress_level: Literal["low", "medium", "high"] = "medium"


class ScoringCriteria(BaseModel):
    """Dynamic A+ scoring criteria that adapt to market conditions.

    Port note: ported verbatim from finwiz's ``schemas/tools/inputs.py::ScoringCriteria``.
    """

    # ETF Criteria
    etf_max_expense_ratio: float = Field(default=0.15, ge=0.0, le=2.0)
    etf_min_aum: float = Field(default=1e9, ge=1e6, le=1e12)
    etf_max_tracking_error: float = Field(default=0.002, ge=0.0, le=0.1)
    etf_min_history_years: int = Field(default=3, ge=1, le=20)

    # Stock Criteria
    stock_min_roe: float = Field(default=0.20, ge=0.0, le=1.0)
    stock_min_revenue_growth: float = Field(default=0.15, ge=-0.5, le=2.0)
    stock_max_debt_to_equity: float = Field(default=0.3, ge=0.0, le=5.0)
    stock_min_market_cap: float = Field(default=1e9, ge=1e6, le=1e13)

    # Crypto Criteria
    crypto_min_market_cap: float = Field(default=10e9, ge=1e6, le=1e13)
    crypto_min_daily_volume: float = Field(default=500e6, ge=1e6, le=1e12)
    crypto_min_age_months: int = Field(default=36, ge=1, le=200)


class APlusScore(BaseModel):
    """Comprehensive A+ score with detailed breakdown.

    Port note: ported verbatim from finwiz's ``schemas/tools/inputs.py::APlusScore``.
    ``grade_info`` stays ``Any`` (finwiz's own annotation) since ``GradeInfo``
    (``tools/analytics/grading.py``) is a plain ``dataclass``, not a Pydantic
    model.
    """

    symbol: str
    asset_type: Literal["etf", "stock", "crypto"]
    composite_score: float = Field(ge=0.0, le=1.0)
    grade_info: Any  # GradeInfo dataclass (tools/analytics/grading.py)

    # Component scores
    fundamental_score: float = Field(ge=0.0, le=1.0)
    technical_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)

    # Analysis details
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    a_plus_rationale: str = ""
    confidence_level: float = Field(default=0.5, ge=0.0, le=1.0)

    # Context
    market_regime: MarketRegime
    scoring_criteria: ScoringCriteria
    analysis_timestamp: Any  # datetime
