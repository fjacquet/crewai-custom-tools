"""Tests for PositionSizingTool and PriceTargetCalculator.

Ported verbatim from finwiz's ``tests/unit/tools/test_position_sizing_tool.py``
and ``tests/unit/tools/test_price_target_calculator.py`` (wave3-tools). Both
tools are pure logic with no I/O — no mocks needed. Only the imports were
adapted to the central package paths; test bodies and assertions are
unchanged.
"""

from datetime import datetime

import pytest
from pytest import approx

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


class TestPositionSizingTool:
    """Test suite for PositionSizingTool."""

    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        return PositionSizingTool()

    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio context."""
        return PortfolioContext(
            total_holdings=10,
            current_allocations={
                "AAPL": 8.0,
                "MSFT": 7.0,
                "GOOGL": 6.0,
                "AMZN": 5.0,
                "TSLA": 4.0,
            },
            sector_allocations={
                "Technology": 30.0,
                "Healthcare": 15.0,
                "Finance": 10.0,
            },
            asset_class_allocations={
                "stock": 90.0,
                "etf": 8.0,
                "crypto": 2.0,
            },
            total_allocated_pct=100.0,
        )

    @pytest.fixture
    def low_risk_holding(self):
        """Create low risk holding profile."""
        return HoldingSizingProfile(
            ticker="JNJ",
            asset_class="stock",
            risk_score=1.5,
            sector="Healthcare",
            current_allocation_pct=0.0,
        )

    @pytest.fixture
    def high_risk_holding(self):
        """Create high risk holding profile."""
        return HoldingSizingProfile(
            ticker="COIN",
            asset_class="stock",
            risk_score=4.5,
            sector="Finance",
            current_allocation_pct=0.0,
        )

    def test_should_calculate_position_size_for_low_risk_holding(self, tool, low_risk_holding, sample_portfolio):
        """Test position sizing for low risk holding."""
        # Arrange - give it some current allocation
        low_risk_holding.current_allocation_pct = 5.0

        # Act
        result = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.recommended_size_pct >= 0
        assert result.recommended_size_pct <= 15.0  # Low risk can be higher
        assert result.sizing_action in ["add", "hold", "trim", "exit"]
        assert len(result.sizing_rationale) > 0

    def test_should_calculate_smaller_size_for_high_risk_holding(self, tool, high_risk_holding, sample_portfolio):
        """Test that high risk holdings get smaller position sizes."""
        # Arrange - give it some current allocation
        high_risk_holding.current_allocation_pct = 3.0

        # Act
        result = tool.calculate_position_size(
            holding=high_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.recommended_size_pct >= 0
        assert result.recommended_size_pct <= 5.0  # High risk should be smaller
        assert result.sizing_action in ["add", "hold", "trim", "exit"]

    def test_should_recommend_add_when_underweight(self, tool, low_risk_holding, sample_portfolio):
        """Test that ADD action is recommended when position is underweight."""
        # Arrange
        low_risk_holding.current_allocation_pct = 1.0  # Very low allocation

        # Act
        result = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        # Should recommend add or hold depending on implementation
        assert result.sizing_action in ["add", "hold"]
        assert result.recommended_size_pct >= result.current_size_pct

    def test_should_recommend_trim_when_overweight(self, tool, sample_portfolio):
        """Test that TRIM action is recommended when position is overweight."""
        # Arrange
        overweight_holding = HoldingSizingProfile(
            ticker="AAPL",
            asset_class="stock",
            risk_score=2.0,
            sector="Technology",
            current_allocation_pct=12.0,  # Over 10% limit
        )

        # Act
        result = tool.calculate_position_size(
            holding=overweight_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.sizing_action == "trim"
        assert result.recommended_size_pct < result.current_size_pct

    def test_should_recommend_hold_when_at_target(self, tool, low_risk_holding, sample_portfolio):
        """Test that HOLD action is recommended when position is at target."""
        # Arrange
        low_risk_holding.current_allocation_pct = 8.0  # Within acceptable range

        # Act
        result = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.sizing_action == "hold"

    def test_should_apply_single_stock_concentration_limit(self, tool, sample_portfolio):
        """Test that single stock concentration limit is enforced."""
        # Arrange
        large_holding = HoldingSizingProfile(
            ticker="NVDA",
            asset_class="stock",
            risk_score=1.0,  # Very low risk
            sector="Technology",
            current_allocation_pct=8.0,  # Give it existing allocation
        )

        # Act
        result = tool.calculate_position_size(
            holding=large_holding,
            portfolio=sample_portfolio,
            risk_tolerance="aggressive",
        )

        # Assert
        assert result.recommended_size_pct <= tool.max_single_stock_pct
        # Concentration limits may be applied
        assert result.concentration_limits_applied in [True, False]

    def test_should_apply_sector_concentration_limit(self, tool, sample_portfolio):
        """Test that sector concentration limit is enforced."""
        # Arrange
        tech_holding = HoldingSizingProfile(
            ticker="NVDA",
            asset_class="stock",
            risk_score=2.0,
            sector="Technology",  # Already at 30%
            current_allocation_pct=0.0,
        )

        # Act
        result = tool.calculate_position_size(
            holding=tech_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        # Should limit size to avoid exceeding 35% sector limit
        assert result.recommended_size_pct <= 5.0  # Can't add much more to tech

    def test_should_apply_crypto_concentration_limit(self, tool, sample_portfolio):
        """Test that crypto concentration limit is enforced."""
        # Arrange
        crypto_holding = HoldingSizingProfile(
            ticker="BTC",
            asset_class="crypto",
            risk_score=4.0,
            sector=None,
            current_allocation_pct=0.0,
        )

        # Act
        result = tool.calculate_position_size(
            holding=crypto_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        # Total crypto should not exceed 10%
        assert result.recommended_size_pct <= (tool.max_crypto_total_pct - sample_portfolio.asset_class_allocations["crypto"])

    def test_should_calculate_risk_contribution(self, tool, high_risk_holding, sample_portfolio):
        """Test that risk contribution is calculated."""
        # Act
        result = tool.calculate_position_size(
            holding=high_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert 0.0 <= result.risk_contribution <= 100.0

    def test_should_calculate_correlation_with_portfolio(self, tool, low_risk_holding, sample_portfolio):
        """Test that correlation with portfolio is calculated."""
        # Act
        result = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert -1.0 <= result.correlation_with_portfolio <= 1.0

    def test_should_adjust_size_for_conservative_risk_tolerance(self, tool, low_risk_holding, sample_portfolio):
        """Test that conservative risk tolerance reduces position sizes."""
        # Arrange - give it existing allocation
        low_risk_holding.current_allocation_pct = 5.0

        # Act
        result_conservative = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="conservative",
        )

        result_aggressive = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="aggressive",
        )

        # Assert
        assert result_conservative.recommended_size_pct <= result_aggressive.recommended_size_pct

    def test_should_adjust_size_for_aggressive_risk_tolerance(self, tool, low_risk_holding, sample_portfolio):
        """Test that aggressive risk tolerance increases position sizes."""
        # Act
        result_moderate = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        result_aggressive = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="aggressive",
        )

        # Assert
        assert result_aggressive.recommended_size_pct >= result_moderate.recommended_size_pct

    def test_should_provide_detailed_rationale(self, tool, low_risk_holding, sample_portfolio):
        """Test that detailed rationale is provided."""
        # Act
        result = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert len(result.sizing_rationale) > 20
        assert result.sizing_rationale is not None

    def test_should_handle_zero_current_allocation(self, tool, low_risk_holding, sample_portfolio):
        """Test handling of new position (zero current allocation)."""
        # Arrange
        low_risk_holding.current_allocation_pct = 0.0

        # Act
        result = tool.calculate_position_size(
            holding=low_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.current_size_pct == approx(0.0)
        # Tool may recommend 0% for new positions or suggest a size
        assert result.recommended_size_pct >= 0.0
        assert result.sizing_action in ["add", "hold"]

    def test_should_handle_etf_position_sizing(self, tool, sample_portfolio):
        """Test position sizing for ETF."""
        # Arrange
        etf_holding = HoldingSizingProfile(
            ticker="SPY",
            asset_class="etf",
            risk_score=1.5,
            sector=None,
            current_allocation_pct=5.0,  # Give it existing allocation
        )

        # Act
        result = tool.calculate_position_size(
            holding=etf_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.recommended_size_pct >= 0
        assert result.sizing_action in ["add", "hold", "trim", "exit"]

    def test_should_handle_crypto_position_sizing(self, tool, sample_portfolio):
        """Test position sizing for crypto."""
        # Arrange
        crypto_holding = HoldingSizingProfile(
            ticker="ETH",
            asset_class="crypto",
            risk_score=4.0,
            sector=None,
            current_allocation_pct=2.0,  # Give it existing allocation
        )

        # Act
        result = tool.calculate_position_size(
            holding=crypto_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.recommended_size_pct >= 0
        assert result.recommended_size_pct <= 5.0  # High risk crypto should be limited

    def test_should_flag_concentration_limits_when_applied(self, tool, sample_portfolio):
        """Test that concentration_limits_applied flag is set correctly."""
        # Arrange
        large_holding = HoldingSizingProfile(
            ticker="MEGA",
            asset_class="stock",
            risk_score=1.0,
            sector="Technology",
            current_allocation_pct=0.0,
        )

        # Act
        result = tool.calculate_position_size(
            holding=large_holding,
            portfolio=sample_portfolio,
            risk_tolerance="aggressive",
        )

        # Assert
        # Should have limits applied due to sector concentration
        if result.recommended_size_pct < 10.0:
            assert result.concentration_limits_applied or result.risk_limits_applied

    def test_should_flag_risk_limits_when_applied(self, tool, high_risk_holding, sample_portfolio):
        """Test that risk_limits_applied flag is set correctly."""
        # Act
        result = tool.calculate_position_size(
            holding=high_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="moderate",
        )

        # Assert
        assert result.risk_limits_applied or result.recommended_size_pct <= 5.0

    def test_should_recommend_exit_for_very_high_risk_with_conservative_tolerance(self, tool, sample_portfolio):
        """Test that EXIT is recommended for very high risk with conservative tolerance."""
        # Arrange
        extreme_risk_holding = HoldingSizingProfile(
            ticker="RISKY",
            asset_class="stock",
            risk_score=5.0,
            sector="Speculative",
            current_allocation_pct=5.0,
        )

        # Act
        result = tool.calculate_position_size(
            holding=extreme_risk_holding,
            portfolio=sample_portfolio,
            risk_tolerance="conservative",
        )

        # Assert
        # Should recommend very small size or exit
        assert result.recommended_size_pct <= 2.0 or result.sizing_action == "exit"


class TestPriceTargetCalculator:
    """Test suite for PriceTargetCalculator."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return PriceTargetCalculator()

    @pytest.fixture
    def stock_fundamentals(self):
        """Create sample stock fundamental data."""
        return FundamentalData(
            earnings_per_share=5.0,
            pe_ratio=20.0,
            book_value_per_share=50.0,
            free_cash_flow=10.0,
            growth_rate=0.15,
        )

    @pytest.fixture
    def etf_fundamentals(self):
        """Create sample ETF fundamental data."""
        return FundamentalData(
            nav=100.0,
            expense_ratio=0.05,
            tracking_error=0.10,
        )

    @pytest.fixture
    def price_history(self):
        """Create sample price history."""
        return PriceHistory(
            prices=[95.0, 98.0, 100.0, 102.0, 105.0, 103.0, 101.0, 99.0, 100.0, 102.0],
            dates=[datetime.now() for _ in range(10)],
            currency="USD",
        )

    def test_should_calculate_targets_for_keep_decision(self, calculator, stock_fundamentals, price_history):
        """Test price target calculation for KEEP recommendation."""
        # Act
        result = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            price_history=price_history,
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert result.current_price == approx(100.0)
        assert result.currency == "USD"
        assert result.fair_value_estimate is not None
        assert result.buy_target_primary is not None
        assert result.sell_target_primary is not None
        assert result.stop_loss_level is not None
        assert len(result.buy_rationale) > 0
        assert len(result.sell_rationale) > 0

    def test_should_calculate_targets_for_sell_decision(self, calculator, stock_fundamentals):
        """Test price target calculation for SELL recommendation."""
        # Act
        result = calculator.calculate_targets(
            ticker="IBM",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            fundamental_data=stock_fundamentals,
            decision="SELL",
        )

        # Assert
        assert result.current_price == approx(100.0)
        assert result.buy_target_primary is None
        assert result.sell_target_primary is not None
        assert "Not recommended" in result.buy_rationale

    def test_should_calculate_targets_for_buy_decision(self, calculator, stock_fundamentals, price_history):
        """Test price target calculation for BUY recommendation."""
        # Act
        result = calculator.calculate_targets(
            ticker="MSFT",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            price_history=price_history,
            fundamental_data=stock_fundamentals,
            decision="BUY",
        )

        # Assert
        assert result.current_price == approx(100.0)
        assert result.buy_target_primary is not None
        assert result.buy_target_secondary is not None
        assert result.sell_target_primary is not None

    def test_should_calculate_stock_fair_value_using_pe_ratio(self, calculator, stock_fundamentals):
        """Test stock fair value calculation using P/E ratio."""
        # Act
        fair_value = calculator._calculate_stock_fair_value(
            current_price=100.0,
            fundamental_data=stock_fundamentals,
        )

        # Assert
        assert fair_value is not None
        assert fair_value > 0
        # With EPS=5.0 and target P/E=17.5, fair value should be around 87.5

    def test_should_calculate_etf_fair_value_using_nav(self, calculator, etf_fundamentals):
        """Test ETF fair value calculation using NAV."""
        # Act
        fair_value = calculator._calculate_etf_fair_value(
            current_price=100.0,
            fundamental_data=etf_fundamentals,
        )

        # Assert
        assert fair_value is not None
        assert fair_value > 0
        # NAV=100.0 with tracking_error=0.10 should give ~99.9

    def test_should_return_none_for_crypto_fair_value(self, calculator):
        """Test that crypto fair value returns None (uses technical analysis)."""
        # Act
        fair_value = calculator._calculate_fair_value(
            asset_class="crypto",
            current_price=50000.0,
            fundamental_data=None,
        )

        # Assert
        assert fair_value is None

    def test_should_calculate_technical_levels_from_price_history(self, calculator, price_history):
        """Test technical support/resistance level calculation."""
        # Act
        support, resistance = calculator._calculate_technical_levels(
            current_price=100.0,
            price_history=price_history,
        )

        # Assert
        assert len(support) >= 0  # May be empty if no valid support levels
        assert len(resistance) >= 0  # May be empty if no valid resistance levels
        # If levels exist, they should be on correct side of current price
        if support:
            assert all(s <= 100.0 for s in support)
        if resistance:
            assert all(r >= 100.0 for r in resistance)

    def test_should_use_percentage_levels_when_no_price_history(self, calculator):
        """Test fallback to percentage-based levels without price history."""
        # Act
        support, resistance = calculator._calculate_technical_levels(
            current_price=100.0,
            price_history=None,
        )

        # Assert
        assert len(support) == 2
        assert len(resistance) == 2
        assert support[0] == approx(95.0)  # 5% below
        assert support[1] == approx(90.0)  # 10% below
        assert resistance[0] == approx(105.0)  # 5% above
        assert resistance[1] == approx(110.0)  # 10% above

    def test_should_calculate_buy_targets_for_keep_decision(self, calculator):
        """Test buy target calculation for KEEP recommendation."""
        # Act
        buy_primary, buy_secondary, rationale = calculator._calculate_buy_targets(
            current_price=100.0,
            fair_value=110.0,
            support_levels=[95.0, 90.0],
            asset_class="stock",
            is_new_position=False,
        )

        # Assert
        assert buy_primary is not None
        assert buy_primary < 100.0  # Should be below current price
        assert len(rationale) > 0

    def test_should_calculate_sell_targets_for_keep_decision(self, calculator):
        """Test sell target calculation for KEEP recommendation."""
        # Act
        (
            sell_primary,
            sell_secondary,
            stop_loss,
            rationale,
        ) = calculator._calculate_sell_targets(
            current_price=100.0,
            fair_value=110.0,
            resistance_levels=[105.0, 110.0],
            asset_class="stock",
            is_keep=True,
        )

        # Assert
        assert sell_primary is not None
        assert sell_primary > 100.0  # Should be above current price
        assert stop_loss is not None
        assert stop_loss < 100.0  # Stop loss should be below current
        assert len(rationale) > 0

    def test_should_calculate_confidence_with_both_fundamental_and_technical(self, calculator):
        """Test confidence calculation with both data types."""
        # Act
        confidence = calculator._calculate_confidence(
            has_fundamental=True,
            has_technical=True,
            fair_value=110.0,
            current_price=100.0,
        )

        # Assert
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should be high with both data types

    def test_should_calculate_lower_confidence_without_fundamental_data(self, calculator):
        """Test that confidence is lower without fundamental data."""
        # Act
        confidence = calculator._calculate_confidence(
            has_fundamental=False,
            has_technical=True,
            fair_value=None,
            current_price=100.0,
        )

        # Assert
        assert 0.0 <= confidence <= 1.0
        assert confidence <= 0.7  # Should be lower or equal without fundamentals

    def test_should_support_multi_currency(self, calculator, stock_fundamentals):
        """Test multi-currency support."""
        # Act
        result_usd = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        result_eur = calculator.calculate_targets(
            ticker="SAP",
            asset_class="stock",
            current_price=100.0,
            currency="EUR",
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert result_usd.currency == "USD"
        assert result_eur.currency == "EUR"

    def test_should_include_data_sources(self, calculator, stock_fundamentals):
        """Test that data sources are included."""
        # Act
        result = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert len(result.data_sources) > 0
        assert isinstance(result.data_sources, list)

    def test_should_include_calculation_method(self, calculator, stock_fundamentals):
        """Test that calculation method is specified."""
        # Act
        result = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert len(result.calculation_method) > 0

    def test_should_include_timestamp(self, calculator, stock_fundamentals):
        """Test that data timestamp is included."""
        # Act
        result = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert result.data_as_of is not None
        assert isinstance(result.data_as_of, datetime)

    def test_should_handle_missing_fundamental_data(self, calculator, price_history):
        """Test handling of missing fundamental data."""
        # Act
        result = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            price_history=price_history,
            fundamental_data=None,
            decision="KEEP",
        )

        # Assert
        assert result.current_price == approx(100.0)
        assert result.fair_value_estimate is None
        assert result.buy_target_primary is not None  # Should still calculate targets

    def test_should_handle_missing_price_history(self, calculator, stock_fundamentals):
        """Test handling of missing price history."""
        # Act
        result = calculator.calculate_targets(
            ticker="AAPL",
            asset_class="stock",
            current_price=100.0,
            currency="USD",
            price_history=None,
            fundamental_data=stock_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert result.current_price == approx(100.0)
        assert result.fair_value_estimate is not None
        assert len(result.support_levels) > 0  # Should use percentage-based levels

    def test_should_calculate_targets_for_etf(self, calculator, etf_fundamentals):
        """Test price target calculation for ETF."""
        # Act
        result = calculator.calculate_targets(
            ticker="SPY",
            asset_class="etf",
            current_price=400.0,
            currency="USD",
            fundamental_data=etf_fundamentals,
            decision="KEEP",
        )

        # Assert
        assert result.current_price == approx(400.0)
        assert result.fair_value_estimate is not None
        assert result.buy_target_primary is not None

    def test_should_calculate_targets_for_crypto(self, calculator):
        """Test price target calculation for crypto."""
        # Arrange
        crypto_history = PriceHistory(
            prices=[48000.0, 49000.0, 50000.0, 51000.0, 50500.0],
            dates=[datetime.now() for _ in range(5)],
            currency="USD",
        )

        # Act
        result = calculator.calculate_targets(
            ticker="BTC",
            asset_class="crypto",
            current_price=50000.0,
            currency="USD",
            price_history=crypto_history,
            fundamental_data=None,
            decision="KEEP",
        )

        # Assert
        assert result.current_price == approx(50000.0)
        assert result.fair_value_estimate is None  # Crypto doesn't use fair value
        assert result.buy_target_primary is not None
