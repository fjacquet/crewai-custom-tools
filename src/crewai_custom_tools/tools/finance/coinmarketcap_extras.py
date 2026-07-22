"""Additional CoinMarketCap tools: listings, news, and historical OHLCV."""

import os
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_CMC_BASE = "https://pro-api.coinmarketcap.com"
_SORT_FIELDS = {"market_cap", "volume_24h", "price", "percent_change_24h"}


def _cmc_key() -> str | None:
    """CoinMarketCap key — the shell-settable name first, header-style name as fallback."""
    return os.environ.get("COINMARKETCAP_API_KEY") or os.environ.get("X-CMC_PRO_API_KEY")


def _cmc_get(path: str, params: dict) -> dict:
    """GET a CoinMarketCap endpoint; raises on HTTP error (turned into err by @api_tool)."""
    resp = requests.get(
        f"{_CMC_BASE}{path}",
        headers={"X-CMC_PRO_API_KEY": _cmc_key() or "", "Accept": "application/json"},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


class CoinMarketCapListInput(BaseModel):
    """Input schema for CoinMarketCapListTool."""

    limit: int = Field(25, description="Number of cryptocurrencies to return (max 100).")
    sort: str = Field(
        "market_cap",
        description="Sort by 'market_cap', 'volume_24h', 'price', or 'percent_change_24h'.",
    )


class CoinMarketCapListTool(BaseTool):
    """List top cryptocurrencies by market cap, volume, price, or 24h change."""

    name: str = "coinmarketcap_list"
    description: str = (
        "Get a list of top cryptocurrencies sorted by market cap, volume, price, or "
        "24h change, with key metrics for each. Requires a CoinMarketCap API key."
    )
    args_schema: type[BaseModel] = CoinMarketCapListInput

    @api_tool(provider="CoinMarketCap", endpoint="Listings")
    def _run(self, limit: int = 25, sort: str = "market_cap") -> str:
        if not _cmc_key():
            return err("CoinMarketCap API key not configured")
        sort_by = sort if sort in _SORT_FIELDS else "market_cap"
        data = _cmc_get(
            "/v1/cryptocurrency/listings/latest",
            {"limit": min(limit, 100), "sort": sort_by, "convert": "USD"},
        )
        listings = []
        for crypto in data.get("data", []):
            quote = crypto.get("quote", {}).get("USD", {})
            listings.append(
                {
                    "rank": crypto.get("cmc_rank"),
                    "name": crypto.get("name"),
                    "symbol": crypto.get("symbol"),
                    "price_usd": quote.get("price"),
                    "percent_change_24h": quote.get("percent_change_24h"),
                    "market_cap_usd": quote.get("market_cap"),
                    "volume_24h_usd": quote.get("volume_24h"),
                }
            )
        return ok({"count": len(listings), "sort": sort_by, "cryptocurrencies": listings})


class CoinMarketCapNewsInput(BaseModel):
    """Input schema for CoinMarketCapNewsTool."""

    symbol: str | None = Field(
        None, description="Optional cryptocurrency symbol (BTC) or slug (bitcoin) to filter news."
    )
    limit: int = Field(10, description="Maximum number of articles to return (max 50).")


class CoinMarketCapNewsTool(BaseTool):
    """Fetch the latest cryptocurrency news, optionally filtered by coin."""

    name: str = "coinmarketcap_news"
    description: str = (
        "Get the latest cryptocurrency news articles, optionally filtered by a coin "
        "symbol or slug. Requires a CoinMarketCap API key."
    )
    args_schema: type[BaseModel] = CoinMarketCapNewsInput

    @api_tool(provider="CoinMarketCap", endpoint="News")
    def _run(self, symbol: str | None = None, limit: int = 10) -> str:
        if not _cmc_key():
            return err("CoinMarketCap API key not configured")
        params: dict = {"limit": min(limit, 50), "sort_by": "published_at"}
        if symbol:
            if symbol.islower():
                params["slug"] = symbol
            else:
                params["symbol"] = symbol.upper()
        data = _cmc_get("/v2/news/latest", params)
        articles = []
        for item in data.get("data") or []:
            source = item.get("source")
            source_name = source.get("name") if isinstance(source, dict) else item.get("source_name")
            articles.append(
                {
                    "title": item.get("title"),
                    "source": source_name,
                    "url": item.get("url"),
                    "published_at": item.get("publishedAt")
                    or item.get("published_at")
                    or item.get("timestamp"),
                    "description": item.get("description") or item.get("subtitle"),
                }
            )
        return ok(
            {"query_filter": symbol or "general", "count": len(articles), "articles": articles}
        )


class CoinMarketCapHistoricalInput(BaseModel):
    """Input schema for CoinMarketCapHistoricalTool."""

    symbol: str = Field(..., description="Cryptocurrency symbol (e.g. BTC, ETH).")
    time_period: str = Field(
        "30d", description="Time window: '24h', '7d', '30d', '3m', '1y', or 'ytd'."
    )


class CoinMarketCapHistoricalTool(BaseTool):
    """Fetch historical price/volume/market-cap points for a cryptocurrency."""

    name: str = "coinmarketcap_historical"
    description: str = (
        "Get historical price, volume, and market cap data for a cryptocurrency over a "
        "time window (24h, 7d, 30d, 3m, 1y, ytd). Requires a CoinMarketCap API key."
    )
    args_schema: type[BaseModel] = CoinMarketCapHistoricalInput

    @api_tool(provider="CoinMarketCap", endpoint="Historical")
    def _run(self, symbol: str, time_period: str = "30d") -> str:
        if not _cmc_key():
            return err("CoinMarketCap API key not configured")
        interval = {
            "24h": "hourly",
            "7d": "daily",
            "30d": "daily",
            "3m": "daily",
            "1y": "weekly",
            "ytd": "daily",
        }.get(time_period, "daily")

        id_data = _cmc_get("/v1/cryptocurrency/map", {"symbol": symbol.upper()})
        ids = id_data.get("data") or []
        if not ids:
            return err(f"No CoinMarketCap id for symbol: {symbol}")

        history = _cmc_get(
            "/v1/cryptocurrency/quotes/historical",
            {"id": ids[0]["id"], "convert": "USD", "interval": interval, "time_period": time_period},
        )
        series = []
        for quote in history.get("data", {}).get("quotes", []):
            usd = quote.get("quote", {}).get("USD", {})
            series.append(
                {
                    "timestamp": quote.get("timestamp"),
                    "price_usd": usd.get("price"),
                    "volume_24h_usd": usd.get("volume_24h"),
                    "market_cap_usd": usd.get("market_cap"),
                }
            )
        return ok(
            {
                "symbol": symbol.upper(),
                "time_period": time_period,
                "interval": interval,
                "historical_data": series,
            }
        )
