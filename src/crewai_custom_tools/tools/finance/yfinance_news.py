"""
Tool for fetching Yahoo Finance News.
"""

import datetime

import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.config.cache import get_cache_manager
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok


class GetTickerNewsInput(BaseModel):
    """Input schema for YahooFinanceNewsTool."""

    ticker: str = Field(
        ..., description="The financial instrument ticker symbol (e.g., AAPL, BTC-USD)"
    )
    limit: int = Field(5, description="The maximum number of news articles to retrieve")


def _parse_news_item(item: dict) -> dict:
    """Normalize a yfinance news item across the modern (nested ``content``) and legacy schemas.

    Modern yfinance nests fields under ``content``; older releases exposed flat keys
    (``title``/``publisher``/``link``/``providerPublishTime``). Support both so a
    yfinance upgrade cannot silently turn every article into placeholder text.
    """
    content = item.get("content")
    if isinstance(content, dict):
        provider = content.get("provider") or {}
        canonical = content.get("canonicalUrl") or {}
        click = content.get("clickThroughUrl") or {}
        return {
            "title": content.get("title") or "No title",
            "publisher": provider.get("displayName") or "Unknown publisher",
            "link": canonical.get("url") or click.get("url") or "#",
            "published_date": content.get("pubDate") or "Unknown date",
        }

    # Legacy flat schema.
    timestamp = item.get("providerPublishTime")
    published = (
        datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
        if timestamp
        else "Unknown date"
    )
    return {
        "title": item.get("title") or "No title",
        "publisher": item.get("publisher") or "Unknown publisher",
        "link": item.get("link") or "#",
        "published_date": published,
    }


class YahooFinanceNewsTool(BaseTool):
    """
    Get recent news for a financial instrument from Yahoo Finance.

    This tool retrieves recent news articles related to a specific stock,
    ETF, or cryptocurrency ticker symbol.
    """

    name: str = "Yahoo Finance News Tool"
    description: str = (
        "Get recent news articles for stocks, ETFs, or cryptocurrencies, "
        "including headlines, publishers, and links to full articles."
    )
    args_schema: type[BaseModel] = GetTickerNewsInput

    @api_tool(provider="YahooFinance", endpoint="News")
    def _run(self, ticker: str, limit: int = 5) -> str:
        """Execute the Yahoo Finance news lookup."""
        cache = get_cache_manager()
        cache_key = f"yahoo_news_{ticker}_{limit}"

        # Try to get from cache first (cache for 15 minutes for news).
        cached_result = cache.get(cache_key, ttl=900)
        if cached_result is not None:
            return str(cached_result)

        news = yf.Ticker(ticker).news or []
        if not news:
            envelope = ok(
                {
                    "ticker": ticker,
                    "news": [],
                    "message": f"No recent news found for {ticker}.",
                }
            )
            cache.set(cache_key, envelope)
            return envelope

        news_list = [_parse_news_item(item) for item in news[:limit]]
        envelope = ok({"ticker": ticker, "news": news_list})
        cache.set(cache_key, envelope)
        return envelope
