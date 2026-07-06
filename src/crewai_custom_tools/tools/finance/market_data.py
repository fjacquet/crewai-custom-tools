"""Macroeconomic and Fundamental Market Data Tools (FRED & Alpha Vantage)."""

import json
import logging
import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Optional
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


class FREDMacroInput(BaseModel):
    """Input model for the FREDMacroTool."""

    indicator: str = Field(
        ...,
        description="The macro indicator to fetch. Options: 'fed_rate' (FEDFUNDS), 'cpi_yoy' (CPIAUCSL), 'unemployment_rate' (UNRATE), 'gdp_growth' (A191RL1Q225SBEA), 'treasury_10y' (DGS10), 'treasury_2y' (DGS2), 'vix' (VIXCLS).",
    )


class FREDMacroTool(BaseTool):
    """A tool to fetch macroeconomic indicator statistics from St. Louis Fed's FRED API."""

    name: str = "FRED Macro Indicators Tool"
    description: str = (
        "Fetches key macro indicators from the Federal Reserve Economic Data (FRED) API. "
        "Supports standard indicators like interest rates, inflation (CPI), unemployment, GDP, yields, and VIX."
    )
    args_schema: type[BaseModel] = FREDMacroInput

    @api_tool(provider="FRED", endpoint="MacroIndicator", default_return="{}")
    def _run(self, indicator: str) -> str:
        """Fetch a single FRED series directly via REST HTTP request."""
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            return json.dumps(
                {"error": "FRED_API_KEY environment variable not configured"}
            )

        # Map human-readable fields to FRED series IDs
        series_map = {
            "fed_rate": "FEDFUNDS",
            "cpi_yoy": "CPIAUCSL",
            "unemployment_rate": "UNRATE",
            "gdp_growth": "A191RL1Q225SBEA",
            "treasury_10y": "DGS10",
            "treasury_2y": "DGS2",
            "vix": "VIXCLS",
        }

        series_id = series_map.get(indicator.lower())
        if not series_id:
            return json.dumps(
                {
                    "error": f"Invalid indicator: {indicator}. Supported options: {list(series_map.keys())}"
                }
            )

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        observations = data.get("observations", [])
        if not observations:
            return json.dumps(
                {"error": f"No observations returned for FRED series: {series_id}"}
            )

        latest_obs = observations[0]
        result = {
            "indicator": indicator,
            "series_id": series_id,
            "date": latest_obs.get("date"),
            "value": latest_obs.get("value"),
            "source": "FRED",
        }
        return json.dumps(result)


class AlphaVantageOverviewInput(BaseModel):
    """Input model for the AlphaVantageOverviewTool."""

    ticker: str = Field(
        ..., description="The stock ticker symbol (e.g., 'AAPL', 'MSFT')."
    )


class AlphaVantageOverviewTool(BaseTool):
    """A tool to fetch company fundamentals overview from Alpha Vantage."""

    name: str = "Alpha Vantage Overview Tool"
    description: str = "Get detailed company fundamental metrics (P/E, Return on Equity, Debt to Equity) from Alpha Vantage."
    args_schema: type[BaseModel] = AlphaVantageOverviewInput

    @api_tool(provider="AlphaVantage", endpoint="Overview", default_return="{}")
    def _run(self, ticker: str) -> str:
        """Fetch fundamental data from Alpha Vantage."""
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_KEY")
        if not api_key:
            return json.dumps({"error": "ALPHA_VANTAGE_API_KEY not configured"})

        url = "https://www.alphavantage.co/query"
        params = {"function": "OVERVIEW", "symbol": ticker.upper(), "apikey": api_key}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check for API-specific error messages
        if "Error Message" in data:
            return json.dumps(
                {"error": f"Alpha Vantage error: {data['Error Message']}"}
            )
        if "Note" in data:
            return json.dumps(
                {"error": f"Alpha Vantage rate limit message: {data['Note']}"}
            )
        if "Symbol" not in data:
            return json.dumps({"error": f"No data returned for ticker {ticker}"})

        def _safe_float(val_str: Optional[str]) -> Optional[float]:
            if val_str is None or val_str in ("None", ""):
                return None
            try:
                return float(val_str)
            except (ValueError, TypeError):
                return None

        result = {
            "symbol": data.get("Symbol"),
            "name": data.get("Name"),
            "return_on_equity_ttm": _safe_float(data.get("ReturnOnEquityTTM")),
            "debt_to_equity_ratio": _safe_float(data.get("DebtToEquityRatio")),
            "quarterly_revenue_growth_yoy": _safe_float(
                data.get("QuarterlyRevenueGrowthYOY")
            ),
            "profit_margin": _safe_float(data.get("ProfitMargin")),
            "pe_ratio": _safe_float(data.get("PERatio")),
            "dividend_yield": _safe_float(data.get("DividendYield")),
            "source": "AlphaVantage",
        }
        return json.dumps(result)
