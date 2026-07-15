"""Yahoo Finance Company Info Tools."""

import logging
from typing import Any

import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok
from crewai_custom_tools.models.finance_models import GetCompanyInfoInput

logger = logging.getLogger(__name__)


class YahooFinanceCompanyInfoTool(BaseTool):
    """Get detailed company information from Yahoo Finance."""

    name: str = "Yahoo Finance Company Info Tool"
    description: str = (
        "Get detailed company information including business description, "
        "key financial metrics, and company profile."
    )
    args_schema: type[BaseModel] = GetCompanyInfoInput

    @api_tool(provider="YahooFinance", endpoint="CompanyInfo")
    def _run(self, ticker: str) -> str:
        """Execute the Yahoo Finance company info lookup."""
        ticker_data = yf.Ticker(ticker)
        info = ticker_data.info

        # Calculate revenue growth from actual financials (more reliable than
        # info["revenueGrowth"]); fall back to the info field on any failure.
        revenue_growth: Any = "N/A"
        try:
            financials = ticker_data.financials
            if not financials.empty and "Total Revenue" in financials.index:
                revenues = financials.loc["Total Revenue"].sort_index(ascending=False)
                if len(revenues) >= 2:
                    latest, previous = revenues.iloc[0], revenues.iloc[1]
                    revenue_growth = (latest - previous) / previous if previous != 0 else "N/A"
        except Exception as exc:  # noqa: BLE001 — any failure here must fall back, not kill the call
            logger.warning(f"Failed to calculate revenue growth for {ticker}: {exc}")
        if revenue_growth == "N/A":
            revenue_growth = info.get("revenueGrowth", "N/A")

        # yfinance returns debtToEquity as a percentage (152.41 = 152.41%);
        # convert to a ratio (1.52) like every other metric here.
        raw_dte = info.get("debtToEquity")
        debt_to_equity = raw_dte / 100 if isinstance(raw_dte, (int, float)) else "N/A"

        # Create a focused company profile
        company_info = {
            "symbol": ticker,
            "name": info.get("longName", "N/A"),
            "industry": info.get("industry", "N/A"),
            "sector": info.get("sector", "N/A"),
            "website": info.get("website", "N/A"),
            "country": info.get("country", "N/A"),
            "employees": info.get("fullTimeEmployees", "N/A"),
            "business_summary": info.get("longBusinessSummary", "N/A"),
            "financial_metrics": {
                "revenue": info.get("totalRevenue", "N/A"),
                "profit_margin": info.get("profitMargins", "N/A"),
                "ebitda": info.get("ebitda", "N/A"),
                "debt_to_equity": debt_to_equity,
                "return_on_equity": info.get("returnOnEquity", "N/A"),
                "revenue_growth": revenue_growth,
                "earnings_growth": info.get("earningsGrowth", "N/A"),
            },
            "valuation_metrics": {
                "market_cap": info.get("marketCap", "N/A"),
                "pe_ratio": info.get("trailingPE", "N/A"),
                "forward_pe": info.get("forwardPE", "N/A"),
                "price_to_book": info.get("priceToBook", "N/A"),
                "price_to_sales": info.get("priceToSalesTrailing12Months", "N/A"),
            },
        }

        # Clean up N/A values
        result = {
            k: v
            if not isinstance(v, dict)
            else {k2: v2 for k2, v2 in v.items() if v2 != "N/A"}
            for k, v in company_info.items()
            if v != "N/A"
        }
        # Additional cleanup for empty metric dicts
        if "financial_metrics" in result and not result["financial_metrics"]:
            del result["financial_metrics"]
        if "valuation_metrics" in result and not result["valuation_metrics"]:
            del result["valuation_metrics"]

        return ok(result)
