"""
Tool for fetching Yahoo Finance Ticker Information.
"""

import contextlib
from datetime import UTC, datetime
from typing import Any

import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.config.cache import get_cache_manager
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok


class GetTickerInfoInput(BaseModel):
    """Input schema for YahooFinanceTickerInfoTool."""

    ticker: str = Field(
        ...,
        description="The stock or financial instrument ticker symbol (e.g., AAPL, TSLA)",
    )


class YahooFinanceTickerInfoTool(BaseTool):
    """
    Get basic information about a financial instrument from Yahoo Finance.

    This tool retrieves key data points about a stock, ETF, or cryptocurrency
    including current price, market cap, 52-week range, and more.
    """

    name: str = "Yahoo Finance Ticker Info Tool"
    description: str = (
        "Get current information about stocks, ETFs, or cryptocurrencies including price,"
        " market cap, P/E ratio, volume, and other key stats."
    )
    args_schema: type[BaseModel] = GetTickerInfoInput

    @api_tool(provider="YahooFinance", endpoint="TickerInfo")
    def _run(self, ticker: str, prefetched_data: dict | None = None) -> str:
        """Execute the Yahoo Finance ticker info lookup."""
        # Batch mode: pre-fetched data short-circuits cache and network entirely.
        if prefetched_data is not None and ticker in prefetched_data:
            cached_info: dict[str, Any] = dict(prefetched_data[ticker])
            cached_info["data_source"] = "prefetched"
            return ok(cached_info)

        cache = get_cache_manager()
        cache_key = f"yahoo_ticker_info_{ticker}"

        # Try to get from cache first (cache for 30 minutes)
        cached_result = cache.get(cache_key, ttl=1800)
        if cached_result is not None:
            return str(cached_result)

        info = yf.Ticker(ticker).info

        # Format a clean subset of the most important information
        fields = {
            "symbol": ticker,
            "name": info.get("shortName", "N/A"),
            "currency": info.get("currency", "N/A"),
            "current_price": info.get(
                "currentPrice", info.get("regularMarketPrice", "N/A")
            ),
            "previous_close": info.get("previousClose", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "volume": info.get("volume", "N/A"),
            "average_volume": info.get("averageVolume", "N/A"),
            "52wk_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52wk_low": info.get("fiftyTwoWeekLow", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "beta": info.get("beta", info.get("beta3Year", "N/A")),
            "return_on_equity": info.get("returnOnEquity", "N/A"),
            "debt_to_equity": info.get("debtToEquity", "N/A"),
            "revenue_growth": info.get("revenueGrowth", "N/A"),
            "profit_margins": info.get("profitMargins", "N/A"),
            "total_assets": info.get("totalAssets", "N/A"),
            "nav_price": info.get("navPrice", "N/A"),
            "expense_ratio": info.get("annualReportExpenseRatio", "N/A"),
        }
        result = {k: v for k, v in fields.items() if v != "N/A"}

        # Only "symbol" survived => yfinance returned nothing usable (invalid/delisted).
        # Signal a failure and do NOT cache it, so a transient miss can recover.
        if set(result) <= {"symbol"}:
            return err(f"No data for ticker {ticker}")

        result["timestamp"] = datetime.now(UTC).isoformat()
        if "regularMarketTime" in info:
            with contextlib.suppress(ValueError, TypeError, OSError):
                result["market_time"] = datetime.fromtimestamp(info["regularMarketTime"], tz=UTC).isoformat()
        result["data_source"] = "live_api"

        envelope = ok(result)
        cache.set(cache_key, envelope)
        return envelope
