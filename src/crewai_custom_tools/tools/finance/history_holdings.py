"""Yahoo Finance Ticker History and ETF Holdings Tools."""

import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok
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

    @api_tool(provider="YahooFinance", endpoint="ETFHoldings")
    def _run(self, ticker: str) -> str:
        """Execute the Yahoo Finance ETF holdings lookup via the funds_data API."""
        etf_data = yf.Ticker(ticker)
        info = etf_data.info

        # ETF holdings/sectors live under funds_data (get_holdings/get_sector_data do
        # NOT exist in yfinance and previously failed silently). funds_data is absent
        # for non-fund tickers, so guard each access.
        holdings: list[dict] = []
        sector_breakdown: dict[str, float] = {}
        funds_data = None
        with suppress(Exception):
            funds_data = etf_data.get_funds_data()

        if funds_data is not None:
            with suppress(Exception):
                top = funds_data.top_holdings
                if top is not None and not top.empty:
                    for symbol, row in top.iterrows():
                        name = row.get("Name")
                        weight = row.get("Holding Percent")
                        holdings.append(
                            {
                                "symbol": str(symbol),
                                "name": str(name) if not pd.isna(name) else "N/A",
                                "weight": float(weight)
                                if not pd.isna(weight)
                                else "N/A",
                            }
                        )
            with suppress(Exception):
                weights = funds_data.sector_weightings
                if isinstance(weights, dict):
                    sector_breakdown = {k: float(v) for k, v in weights.items()}

        result = {
            "symbol": ticker,
            "name": info.get("shortName", "N/A"),
            "asset_class": info.get("categoryName", "N/A"),
            "expense_ratio": info.get("annualReportExpenseRatio", "N/A"),
            "aum": info.get("totalAssets", "N/A"),
            "top_holdings": holdings[:10],
            "sector_breakdown": sector_breakdown,
        }

        # Strip empty/placeholder values (including an empty sector_breakdown dict).
        cleaned = {k: v for k, v in result.items() if v not in ("N/A", [], {})}
        return ok(cleaned)


class YahooFinanceHistoryTool(BaseTool):
    """Get historical price data for a financial instrument from Yahoo Finance."""

    name: str = "Yahoo Finance History Tool"
    description: str = (
        "Get historical price data (open, high, low, close, volume) for stocks, ETFs, "
        "or cryptocurrencies over various time periods and intervals."
    )
    args_schema: type[BaseModel] = GetTickerHistoryInput

    @api_tool(provider="YahooFinance", endpoint="History")
    def _run(self, ticker: str, period: str = "1y", interval: str = "1d", prefetched_data: dict | None = None) -> str:
        """Execute the Yahoo Finance historical data lookup."""
        if prefetched_data is not None and ticker in prefetched_data:
            cached_history: dict[str, Any] = dict(prefetched_data[ticker])
            cached_history["data_source"] = "prefetched"
            return ok(cached_history)

        ticker_data = yf.Ticker(ticker)
        history = ticker_data.history(period=period, interval=interval)

        if history.empty:
            return ok({"symbol": ticker, "history": [], "message": f"No historical data for {ticker}"})

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

        latest = history_list[-1] if history_list else {}
        earliest = history_list[0] if history_list else {}
        earliest_close = earliest.get("close")
        latest_close = latest.get("close")

        # Divide by the REAL earliest close; a genuine 0/None earliest yields None
        # rather than a fabricated percentage from dividing by 1.
        if earliest_close and latest_close is not None:
            price_change_percent = round((latest_close / earliest_close - 1) * 100, 2)
        else:
            price_change_percent = None

        summary = {
            "symbol": ticker,
            "period": period,
            "interval": interval,
            "start_date": earliest.get("date", "N/A"),
            "end_date": latest.get("date", "N/A"),
            "price_change": round((latest_close or 0) - (earliest_close or 0), 2),
            "price_change_percent": price_change_percent,
            "data_points": len(history_list),
        }

        payload: dict[str, Any] = {
            "summary": summary,
            "history": history_list[-10:],
            "timestamp": datetime.now(UTC).isoformat(),
            "data_source": "live_api",
        }
        if history_list:
            try:
                payload["data_time"] = (
                    datetime.strptime(history_list[-1]["date"], "%Y-%m-%d").replace(tzinfo=UTC).isoformat()
                )
            except ValueError:
                logger.warning(f"Could not parse latest bar date for {ticker}")
        return ok(payload)
