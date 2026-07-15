"""SEC EDGAR filings + key financial facts (built fresh).

Keyless, but the SEC requires a descriptive User-Agent on every request. All data
comes straight from EDGAR's public JSON APIs — no fabricated values.
"""

from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

_HEADERS = {"User-Agent": "crewai-custom-tools research contact@example.com"}
_KEY_FACTS = ("Revenues", "NetIncomeLoss", "Assets", "Liabilities", "StockholdersEquity")


class SECAnalysisInput(BaseModel):
    """Input schema for EnhancedSECAnalysisTool."""

    ticker: str = Field(
        ..., description="The stock ticker to analyze via SEC EDGAR (e.g. 'AAPL')."
    )
    filing_count: int = Field(
        5, description="Max number of recent 10-K/10-Q filings to return."
    )


def _ticker_to_cik(ticker: str) -> Optional[int]:
    """Resolve a ticker to its zero-padded SEC CIK, or None if unknown."""
    resp = requests.get(
        "https://www.sec.gov/files/company_tickers.json", headers=_HEADERS, timeout=15
    )
    resp.raise_for_status()
    up = ticker.upper()
    for row in resp.json().values():
        if row.get("ticker") == up:
            return int(row["cik_str"])
    return None


def _latest_annual_fact(companyfacts: dict, concept: str) -> Optional[dict]:
    """Latest annual (10-K / FY) USD value for a us-gaap concept, or None."""
    node = companyfacts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not node:
        return None
    units = node.get("units", {})
    series = units.get("USD") or next(iter(units.values()), [])
    annual = [
        u
        for u in series
        if u.get("form") == "10-K" and u.get("fp") == "FY" and u.get("val") is not None
    ]
    if not annual:
        return None
    latest = max(annual, key=lambda u: u.get("end", ""))
    return {
        "value": latest["val"],
        "period_end": latest.get("end"),
        "fiscal_year": latest.get("fy"),
    }


class EnhancedSECAnalysisTool(BaseTool):
    """Fetch recent SEC filings and key annual financials for a ticker from EDGAR."""

    name: str = "sec_edgar_analysis"
    description: str = (
        "Look up a company on SEC EDGAR by ticker and return its recent 10-K/10-Q filings "
        "(form, dates, document URL) plus the latest annual financial facts "
        "(revenue, net income, assets, liabilities, equity) from XBRL company facts."
    )
    args_schema: type[BaseModel] = SECAnalysisInput

    @api_tool(provider="SECEdgar", endpoint="Filings", timeout=45.0)
    def _run(self, ticker: str, filing_count: int = 5) -> str:
        cik = _ticker_to_cik(ticker)
        if cik is None:
            return err(f"No SEC CIK found for ticker {ticker!r}")

        sub_resp = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
            headers=_HEADERS,
            timeout=15,
        )
        sub_resp.raise_for_status()
        sub = sub_resp.json()
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        report_dates = recent.get("reportDate", [""] * len(forms))
        primary_docs = recent.get("primaryDocument", [""] * len(forms))

        filings: list[dict] = []
        for i, form in enumerate(forms):
            if form not in ("10-K", "10-Q"):
                continue
            accession = recent["accessionNumber"][i]
            filings.append(
                {
                    "form": form,
                    "filing_date": recent["filingDate"][i],
                    "report_date": report_dates[i],
                    "accession": accession,
                    "url": (
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                        f"{accession.replace('-', '')}/{primary_docs[i]}"
                    ),
                }
            )
            if len(filings) >= filing_count:
                break

        facts_resp = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
            headers=_HEADERS,
            timeout=30,
        )
        facts_resp.raise_for_status()
        companyfacts = facts_resp.json()
        financials = {
            concept: fact
            for concept in _KEY_FACTS
            if (fact := _latest_annual_fact(companyfacts, concept)) is not None
        }

        return ok(
            {
                "ticker": ticker.upper(),
                "cik": cik,
                "company": sub.get("name"),
                "sic_description": sub.get("sicDescription"),
                "recent_filings": filings,
                "latest_annual_financials": financials,
            }
        )
