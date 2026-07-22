"""Multi-criteria stock screener over Yahoo Finance (built fresh, not ported).

Only real yfinance data is used: a ticker missing a field simply fails the filter
that needs it — no fabricated values.
"""

from typing import Optional

import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok

# Screening metric -> yfinance `info` field.
_METRICS = {
    "name": "shortName",
    "sector": "sector",
    "market_cap": "marketCap",
    "pe_ratio": "trailingPE",
    "dividend_yield": "dividendYield",
    "volume": "averageVolume",
}
_NUMERIC_SORT = {"market_cap", "pe_ratio", "dividend_yield", "volume"}


class MarketScreeningInput(BaseModel):
    """Input schema for MarketScreeningTool."""

    tickers: list[str] = Field(
        ..., description="Ticker symbols to screen (e.g. ['AAPL', 'MSFT'])."
    )
    min_market_cap: float | None = Field(
        None, description="Minimum market capitalization in USD."
    )
    max_pe: float | None = Field(None, description="Maximum trailing P/E ratio.")
    min_dividend_yield: float | None = Field(
        None, description="Minimum dividend yield as a fraction (e.g. 0.02 for 2%)."
    )
    sector: str | None = Field(
        None, description="Required sector (case-insensitive exact match)."
    )
    min_volume: float | None = Field(
        None, description="Minimum average daily volume."
    )
    sort_by: str = Field(
        "market_cap",
        description="Sort matches by: market_cap, pe_ratio, dividend_yield, volume.",
    )


def _extract_metrics(info: dict) -> dict:
    """Pull the screening metrics from a yfinance info dict (missing field -> None)."""
    return {key: info.get(field) for key, field in _METRICS.items()}


def _passes(m: dict, crit: MarketScreeningInput) -> bool:
    """True only if every provided filter is satisfied; missing data fails that filter."""
    if crit.min_market_cap is not None and (
        m["market_cap"] is None or m["market_cap"] < crit.min_market_cap
    ):
        return False
    if crit.max_pe is not None and (m["pe_ratio"] is None or m["pe_ratio"] > crit.max_pe):
        return False
    if crit.min_dividend_yield is not None and (
        m["dividend_yield"] is None or m["dividend_yield"] < crit.min_dividend_yield
    ):
        return False
    if crit.sector is not None and (
        m["sector"] is None or m["sector"].lower() != crit.sector.lower()
    ):
        return False
    return not (
        crit.min_volume is not None
        and (m["volume"] is None or m["volume"] < crit.min_volume)
    )


class MarketScreeningTool(BaseTool):
    """Screen a set of tickers against fundamental criteria using Yahoo Finance."""

    name: str = "market_screening"
    description: str = (
        "Screen a list of stock tickers against fundamental criteria (market cap, P/E, "
        "dividend yield, sector, average volume) using live Yahoo Finance data, and rank "
        "the matches. Tickers missing a required metric are excluded from that filter."
    )
    args_schema: type[BaseModel] = MarketScreeningInput

    @api_tool(provider="YahooFinance", endpoint="Screening", timeout=60.0)
    def _run(
        self,
        tickers: list[str],
        min_market_cap: float | None = None,
        max_pe: float | None = None,
        min_dividend_yield: float | None = None,
        sector: str | None = None,
        min_volume: float | None = None,
        sort_by: str = "market_cap",
    ) -> str:
        criteria = MarketScreeningInput(
            tickers=tickers,
            min_market_cap=min_market_cap,
            max_pe=max_pe,
            min_dividend_yield=min_dividend_yield,
            sector=sector,
            min_volume=min_volume,
            sort_by=sort_by,
        )

        matches: list[dict] = []
        errored: list[str] = []
        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info or {}
            except Exception:
                errored.append(ticker)
                continue
            metrics = _extract_metrics(info)
            if _passes(metrics, criteria):
                matches.append({"symbol": ticker, **metrics})

        sort_key = sort_by if sort_by in _NUMERIC_SORT else "market_cap"
        # Descending by the chosen metric, tickers missing it sorted last.
        matches.sort(key=lambda m: (m.get(sort_key) is None, -(m.get(sort_key) or 0)))

        return ok(
            {
                "matches": matches,
                "screened": len(tickers),
                "matched": len(matches),
                "errored": errored,
                "criteria": {
                    k: v
                    for k, v in criteria.model_dump().items()
                    if k not in ("tickers", "sort_by") and v is not None
                },
                "sorted_by": sort_key,
            }
        )
