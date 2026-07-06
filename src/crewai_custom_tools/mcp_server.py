"""Model Context Protocol (MCP) server for crewai-custom-tools.

Exposes our premium consolidated tools (Web search, stock history, crypto prices,
OSINT domain recon, and HTML/PDF document compilers) directly to any MCP client
(e.g., Cursor, Windsurf, or Claude Desktop) via stdio JSON-RPC channels.
"""

import json
import os
from typing import Any, List, Optional
from mcp.server.fastmcp import FastMCP

# Instantiate our FastMCP server named "crewai-custom-tools"
mcp = FastMCP("crewai-custom-tools")


# ==============================================================================
# 1. Web Search & Scraping Tools
# ==============================================================================


@mcp.tool()
def search_perplexity(query: str, focus: str = "internet") -> str:
    """Run a resilient web-grounded AI-synthesized search query on Perplexity.

    Args:
        query: The search question or keywords to search for.
        focus: Search scope. Options: 'internet', 'news', 'academic', 'reddit'.
    """
    from crewai_custom_tools import PerplexitySearchTool

    tool = PerplexitySearchTool()
    return tool._run(query=query, focus=focus)


@mcp.tool()
def search_google(query: str) -> str:
    """Search Google organic listings for up-to-date information on any topic using Serper.dev.

    Args:
        query: The search query to search Google for.
    """
    from crewai_custom_tools import SerperSearchTool

    tool = SerperSearchTool()
    return tool._run(query=query)


@mcp.tool()
def scrape_website(url: str, provider: Optional[str] = None) -> str:
    """Scrape raw text and body content from any website URL.

    Automatically escalates through ScrapeNinja proxy or Firecrawl APIs if blocked by Cloudflare or JS.

    Args:
        url: The website URL to scrape.
        provider: Optional override. Options: 'standard' (BeautifulSoup), 'scrapeninja', 'firecrawl'.
    """
    from crewai_custom_tools import UnifiedScraperTool

    tool = UnifiedScraperTool()
    return tool._run(url=url, provider=provider)


# ==============================================================================
# 2. Quantitative Finance & Macroeconomic Tools
# ==============================================================================


@mcp.tool()
def get_stock_metrics(ticker: str) -> str:
    """Get key financial statistics (P/E ratio, market cap, beta, profit margins) for a stock ticker from Yahoo Finance.

    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'TSLA').
    """
    from crewai_custom_tools import YahooFinanceTickerInfoTool

    tool = YahooFinanceTickerInfoTool()
    return tool._run(ticker=ticker)


@mcp.tool()
def get_etf_holdings(ticker: str) -> str:
    """Get detailed top-10 holdings, sector allocations, and assets under management (AUM) for an ETF.

    Args:
        ticker: The ETF ticker symbol (e.g., 'VOO', 'QQQ').
    """
    from crewai_custom_tools import YahooFinanceETFHoldingsTool

    tool = YahooFinanceETFHoldingsTool()
    return tool._run(ticker=ticker)


@mcp.tool()
def get_macro_indicator(indicator: str) -> str:
    """Fetch key macroeconomic indicators (FED funds rate, inflation CPI, unemployment, Treasury yields) from FRED.

    Args:
        indicator: Options: 'fed_rate', 'cpi_yoy', 'unemployment_rate', 'gdp_growth', 'treasury_10y', 'vix'.
    """
    from crewai_custom_tools import FREDMacroTool

    tool = FREDMacroTool()
    return tool._run(indicator=indicator)


@mcp.tool()
def get_crypto_quote(symbol: str) -> str:
    """Fetch real-time price, 24h/7d change, and rank statistics for any cryptocurrency from CoinMarketCap.

    Args:
        symbol: The cryptocurrency symbol (e.g., 'BTC', 'ETH', 'SOL').
    """
    from crewai_custom_tools import CoinMarketCapInfoTool

    tool = CoinMarketCapInfoTool()
    return tool._run(symbol=symbol)


# ==============================================================================
# 3. OSINT & Reconnaissance Tools
# ==============================================================================


@mcp.tool()
def search_github(query: str, search_type: str = "repositories") -> str:
    """Search GitHub for repositories, code chunks, issues, or users.

    Args:
        query: The search query string.
        search_type: Options: 'repositories', 'code', 'issues', 'users'.
    """
    from crewai_custom_tools import GitHubSearchTool

    tool = GitHubSearchTool()
    return tool._run(query=query, search_type=search_type)


@mcp.tool()
def search_username(username: str) -> str:
    """Scan major social platforms (GitHub, Reddit, Instagram, etc.) to see if a username is registered."""
    from crewai_custom_tools import UsernameSearchTool

    tool = UsernameSearchTool()
    return tool._run(username=username)


@mcp.tool()
def search_french_business_registry(query: str) -> str:
    """Query the official, keyless French corporate register (recherche-entreprises) for company metadata, SIREN, and directors.

    Args:
        query: A 9-digit SIREN registration number or a free-text company name (e.g., 'LVMH').
    """
    from crewai_custom_tools import FrenchRegistryTool

    tool = FrenchRegistryTool()
    return tool._run(query=query)


# ==============================================================================
# 4. Report Document Compilation Tools
# ==============================================================================


@mcp.tool()
def compile_html_to_pdf(html_file_path: str, output_pdf_path: str) -> str:
    """Compile any local HTML document/report into a professional PDF file using WeasyPrint.

    Args:
        html_file_path: Absolute or relative path to the input HTML file.
        output_pdf_path: Path where the generated PDF should be written.
    """
    from crewai_custom_tools import HtmlToPdfTool

    tool = HtmlToPdfTool()
    return tool._run(html_file_path=html_file_path, output_pdf_path=output_pdf_path)


# ==============================================================================
# 5. Workspace Integrations
# ==============================================================================


@mcp.tool()
def get_current_weather(location: str) -> str:
    """Get the current weather and meteorological conditions for a city from AccuWeather.

    Args:
        location: The city name (e.g., 'London', 'Paris').
    """
    from crewai_custom_tools import AccuWeatherTool

    tool = AccuWeatherTool()
    return tool._run(location=location)


def run() -> None:
    """Launch the FastMCP stdio server (configured as a console entrypoint)."""
    mcp.run()
