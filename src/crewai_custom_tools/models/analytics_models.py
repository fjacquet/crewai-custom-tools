"""Pydantic models for the analytics tools (valuation, ETF metrics, regulatory
compliance, position sizing, price targets).
"""

from datetime import datetime
from typing import Literal

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
