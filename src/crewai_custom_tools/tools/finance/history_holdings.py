"""Yahoo Finance Ticker History and ETF Holdings Tools."""

import json
import logging
from contextlib import suppress
import pandas as pd
import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.models.finance_models import (
    GetETFHoldingsInput,
    GetTickerHistoryInput,
)

logger = logging.getLogger(__name__)


class YahooFinanceETFHoldingsTool(BaseTool):
    """Get holdings information for an ETF from Yahoo Finance."""

    name: str = "Yahoo Finance ETF Holdings Tool"
    description: str = (
        "Get detailed holdings information for ETFs, including top holdings, "
        "sector allocations, and asset breakdown."
    )
    args_schema: type[BaseModel] = GetETFHoldingsInput

    @api_tool(provider="YahooFinance", endpoint="ETFHoldings", default_return="{}")
    def _run(self, ticker: str) -> str:
        """Execute the Yahoo Finance ETF holdings lookup."""
        etf_data = yf.Ticker(ticker)

        # Get basic ETF info
        info = etf_data.info

        # Get holdings if available
        holdings = []
        with suppress(Exception):
            holdings_data = etf_data.get_holdings()
            if holdings_data is not None and not holdings_data.empty:
                for symbol, row in holdings_data.iterrows():
                    holding = {
                        "symbol": symbol,
                        "name": row.get("Name")
                        if not pd.isna(row.get("Name"))
                        else "N/A",
                        "weight": row.get("% Assets")
                        if not pd.isna(row.get("% Assets"))
                        else "N/A",
                        "shares": row.get("Shares")
                        if not pd.isna(row.get("Shares"))
                        else "N/A",
                    }
                    holdings.append(holding)

        # Get sector breakdown if available
        sector_data = {}
        with suppress(Exception):
            sector_data = etf_data.get_sector_data()
            if isinstance(sector_data, dict):
                sector_data = {k: float(v) for k, v in sector_data.items()}

        result = {
            "symbol": ticker,
            "name": info.get("shortName", "N/A"),
            "asset_class": info.get("categoryName", "N/A"),
            "expense_ratio": info.get("annualReportExpenseRatio", "N/A"),
            "aum": info.get("totalAssets", "N/A"),
            "top_holdings": holdings[:10],  # Top 10 holdings
            "sector_breakdown": sector_data,
        }

        final_result = {k: v for k, v in result.items() if v != "N/A" and v != []}
        return json.dumps(final_result)


class YahooFinanceHistoryTool(BaseTool):
    """Get historical price data for a financial instrument from Yahoo Finance."""

    name: str = "Yahoo Finance History Tool"
    description: str = (
        "Get historical price data (open, high, low, close, volume) for stocks, ETFs, "
        "or cryptocurrencies over various time periods and intervals."
    )
    args_schema: type[BaseModel] = GetTickerHistoryInput

    @api_tool(provider="YahooFinance", endpoint="History", default_return="{}")
    def _run(self, ticker: str, period: str = "1y", interval: str = "1d") -> str:
        """Execute the Yahoo Finance historical data lookup."""
        ticker_data = yf.Ticker(ticker)
        history = ticker_data.history(period=period, interval=interval)

        if history.empty:
            return json.dumps({"error": f"No historical data available for {ticker}"})

        # Format the data for easier consumption
        history_list = []
        for date, row in history.iterrows():
            history_list.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "open": round(
                        float(val) if not pd.isna(val := row.get("Open")) else 0.0, 2
                    ),
                    "high": round(
                        float(val) if not pd.isna(val := row.get("High")) else 0.0, 2
                    ),
                    "low": round(
                        float(val) if not pd.isna(val := row.get("Low")) else 0.0, 2
                    ),
                    "close": round(
                        float(val) if not pd.isna(val := row.get("Close")) else 0.0, 2
                    ),
                    "volume": int(val) if not pd.isna(val := row.get("Volume")) else 0,
                }
            )

        # Add summary statistics
        latest = history_list[-1] if history_list else {}
        earliest = history_list[0] if history_list else {}

        summary = {
            "symbol": ticker,
            "period": period,
            "interval": interval,
            "start_date": earliest.get("date", "N/A"),
            "end_date": latest.get("date", "N/A"),
            "price_change": round(latest.get("close", 0) - earliest.get("close", 0), 2),
            "price_change_percent": round(
                (
                    latest.get("close", 0)
                    / (div if (div := earliest.get("close")) and div != 0 else 1)
                    - 1
                )
                * 100,
                2,
            ),
            "data_points": len(history_list),
        }

        result = {
            "summary": summary,
            "history": history_list[
                -10:
            ],  # Return only last 10 data points to avoid overloading
        }
        return json.dumps(result)
