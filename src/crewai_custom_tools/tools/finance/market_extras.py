"""Additional market data tools: Alpha Vantage news sentiment and Chart-img images."""

import base64
import os
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
_CHART_IMG_URL = "https://api.chart-img.com/v1/stock"


class AlphaVantageNewsSentimentInput(BaseModel):
    """Input schema for AlphaVantageNewsSentimentTool."""

    tickers: str = Field(..., description="Comma-separated tickers, e.g. 'AAPL,MSFT'.")
    sort: str = Field("LATEST", description="Sort order: LATEST, EARLIEST, RELEVANCE.")
    time_from: Optional[str] = Field(None, description="Start time, YYYYMMDDTHHMM.")
    time_to: Optional[str] = Field(None, description="End time, YYYYMMDDTHHMM.")
    limit: int = Field(50, description="Max number of articles.")
    topics: Optional[str] = Field(None, description="Comma-separated topics filter.")


class AlphaVantageNewsSentimentTool(BaseTool):
    """Fetch news and sentiment for tickers via the Alpha Vantage NEWS_SENTIMENT endpoint."""

    name: str = "alpha_vantage_news_sentiment"
    description: str = (
        "Fetches recent news articles and their sentiment scores for one or more tickers "
        "using Alpha Vantage's NEWS_SENTIMENT endpoint. Requires ALPHA_VANTAGE_API_KEY."
    )
    args_schema: type[BaseModel] = AlphaVantageNewsSentimentInput

    @api_tool(provider="AlphaVantage", endpoint="NewsSentiment")
    def _run(
        self,
        tickers: str,
        sort: str = "LATEST",
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = 50,
        topics: Optional[str] = None,
    ) -> str:
        """Fetch news + sentiment from Alpha Vantage."""
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_KEY")
        if not api_key:
            return err("ALPHA_VANTAGE_API_KEY not configured")

        params: dict = {
            "function": "NEWS_SENTIMENT",
            "tickers": tickers,
            "sort": sort,
            "limit": limit,
            "apikey": api_key,
        }
        if time_from:
            params["time_from"] = time_from
        if time_to:
            params["time_to"] = time_to
        if topics:
            params["topics"] = topics

        resp = requests.get(_ALPHA_VANTAGE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if "Error Message" in data:
            return err(f"Alpha Vantage error: {data['Error Message']}")
        # AV signals rate limiting via 'Note' / 'Information' rather than an HTTP error.
        if "Note" in data or "Information" in data:
            return err(f"Alpha Vantage rate limit: {data.get('Note') or data.get('Information')}")
        return ok(data)


class ChartImgInput(BaseModel):
    """Input schema for ChartImgTool."""

    symbol: str = Field(..., description="Ticker symbol, e.g. 'AAPL'.")
    interval: str = Field("1day", description="Chart interval.")
    range: str = Field("6mo", description="Chart date range, e.g. '6mo', '1y'.")
    width: int = Field(900, description="Image width in pixels.")
    height: int = Field(500, description="Image height in pixels.")
    theme: str = Field("light", description="Chart theme: 'light' or 'dark'.")


class ChartImgTool(BaseTool):
    """Generate a PNG price chart via the Chart-img API, returned as a base64 data URL."""

    name: str = "chart_img"
    description: str = (
        "Generates a PNG price chart for a symbol via the Chart-img API and returns it as "
        "a base64 data URL suitable for embedding in HTML. Requires CHART_IMG_API_KEY."
    )
    args_schema: type[BaseModel] = ChartImgInput

    @api_tool(provider="ChartImg", endpoint="Chart")
    def _run(
        self,
        symbol: str,
        interval: str = "1day",
        range: str = "6mo",
        width: int = 900,
        height: int = 500,
        theme: str = "light",
    ) -> str:
        """Fetch a chart image and encode it as a data URL."""
        api_key = os.getenv("CHART_IMG_API_KEY")
        if not api_key:
            return err("CHART_IMG_API_KEY not configured")

        resp = requests.get(
            _CHART_IMG_URL,
            headers={"x-api-key": api_key},
            params={
                "symbol": symbol,
                "interval": interval,
                "range": range,
                "width": str(width),
                "height": str(height),
                "theme": theme,
            },
            timeout=20,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/png")
        b64 = base64.b64encode(resp.content).decode("ascii")
        return ok({"data_url": f"data:{content_type};base64,{b64}", "content_type": content_type})
