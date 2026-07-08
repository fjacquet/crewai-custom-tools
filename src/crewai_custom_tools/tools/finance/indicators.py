"""Twelve Data technical-indicator tools (RSI, MACD, Bollinger Bands)."""

import os
from typing import List, Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_BASE_URL = "https://api.twelvedata.com"


def _fetch_indicator(indicator: str, params: dict) -> dict:
    """Fetch one indicator series from Twelve Data and return the parsed JSON."""
    resp = requests.get(f"{_BASE_URL}/{indicator}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


class TwelveDataIndicatorInput(BaseModel):
    """Input schema for TwelveDataIndicatorTool."""

    symbol: str = Field(..., description="Ticker symbol, e.g. 'AAPL' or 'BTC/USD'.")
    indicator: str = Field("rsi", description="Indicator: 'rsi', 'macd', or 'bbands'.")
    interval: str = Field("1day", description="Time interval, e.g. '1day', '1h'.")
    length: Optional[int] = Field(None, description="Period for rsi/bbands (time_period).")
    fast_period: Optional[int] = Field(None, description="MACD fast period.")
    slow_period: Optional[int] = Field(None, description="MACD slow period.")
    signal_period: Optional[int] = Field(None, description="MACD signal period.")
    outputsize: int = Field(100, description="Number of data points to return.")


class TwelveDataIndicatorTool(BaseTool):
    """Fetch a single technical indicator (RSI/MACD/BBANDS) from Twelve Data."""

    name: str = "twelve_data_indicator"
    description: str = (
        "Fetches a technical indicator (RSI, MACD, or Bollinger Bands) for a symbol from "
        "the Twelve Data API. Requires TWELVE_DATA_API_KEY."
    )
    args_schema: type[BaseModel] = TwelveDataIndicatorInput

    @api_tool(provider="TwelveData", endpoint="Indicator")
    def _run(
        self,
        symbol: str,
        indicator: str = "rsi",
        interval: str = "1day",
        length: Optional[int] = None,
        fast_period: Optional[int] = None,
        slow_period: Optional[int] = None,
        signal_period: Optional[int] = None,
        outputsize: int = 100,
    ) -> str:
        """Fetch a technical indicator series from Twelve Data."""
        api_key = os.getenv("TWELVE_DATA_API_KEY")
        if not api_key:
            return err("TWELVE_DATA_API_KEY not configured")

        params: dict = {
            "symbol": symbol,
            "interval": interval,
            "apikey": api_key,
            "outputsize": outputsize,
        }
        if indicator in ("rsi", "bbands") and length is not None:
            params["time_period"] = length
        if indicator == "macd":
            if fast_period is not None:
                params["fast"] = fast_period
            if slow_period is not None:
                params["slow"] = slow_period
            if signal_period is not None:
                params["signal"] = signal_period

        data = _fetch_indicator(indicator, params)
        if isinstance(data, dict) and data.get("status") == "error":
            return err(f"Twelve Data: {data.get('message', 'unknown error')}")
        return ok(data)


class TwelveDataMultiIndicatorInput(BaseModel):
    """Input schema for TwelveDataMultiIndicatorTool."""

    symbol: str = Field(..., description="Ticker symbol, e.g. 'AAPL' or 'BTC/USD'.")
    interval: str = Field("1day", description="Time interval, e.g. '1day', '1h'.")
    indicators: Optional[List[str]] = Field(
        None, description="Indicators to fetch; defaults to ['rsi', 'macd', 'bbands']."
    )
    rsi_period: int = Field(14, description="RSI period.")
    macd_fast: int = Field(12, description="MACD fast period.")
    macd_slow: int = Field(26, description="MACD slow period.")
    macd_signal: int = Field(9, description="MACD signal period.")
    bbands_period: int = Field(20, description="Bollinger Bands period.")
    bbands_stddev: int = Field(2, description="Bollinger Bands standard deviations.")
    outputsize: int = Field(100, description="Number of data points to return.")


class TwelveDataMultiIndicatorTool(BaseTool):
    """Fetch RSI, MACD, and Bollinger Bands from Twelve Data in one call."""

    name: str = "twelve_data_multi_indicator"
    description: str = (
        "Fetches multiple technical indicators (RSI, MACD, Bollinger Bands) for a symbol "
        "from Twelve Data in a single call. Requires TWELVE_DATA_API_KEY."
    )
    args_schema: type[BaseModel] = TwelveDataMultiIndicatorInput

    @api_tool(provider="TwelveData", endpoint="MultiIndicator")
    def _run(
        self,
        symbol: str,
        interval: str = "1day",
        indicators: Optional[List[str]] = None,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bbands_period: int = 20,
        bbands_stddev: int = 2,
        outputsize: int = 100,
    ) -> str:
        """Fetch several technical indicators, returning each under its own key."""
        api_key = os.getenv("TWELVE_DATA_API_KEY")
        if not api_key:
            return err("TWELVE_DATA_API_KEY not configured")

        indicators = indicators or ["rsi", "macd", "bbands"]
        extra_params = {
            "rsi": {"time_period": rsi_period, "outputsize": outputsize},
            "macd": {
                "fast": macd_fast,
                "slow": macd_slow,
                "signal": macd_signal,
                "outputsize": outputsize,
            },
            "bbands": {
                "time_period": bbands_period,
                "sd": bbands_stddev,
                "outputsize": outputsize,
            },
        }

        results: dict = {}
        for indicator in indicators:
            base = {"symbol": symbol, "interval": interval, "apikey": api_key}
            try:
                results[indicator] = _fetch_indicator(
                    indicator, {**base, **extra_params.get(indicator, {})}
                )
            except requests.exceptions.RequestException as exc:
                results[indicator] = {"error": str(exc)}

        return ok({"symbol": symbol, "interval": interval, "indicators": results})
