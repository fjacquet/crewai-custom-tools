"""Centralized CrewAI custom tools library."""

__version__ = "0.1.1"

# 1. Web Search & Scraping
from crewai_custom_tools.tools.web.perplexity import PerplexitySearchTool
from crewai_custom_tools.tools.web.serper import SerperSearchTool
from crewai_custom_tools.tools.web.scraper import (
    UnifiedScraperTool,
    ScrapeNinjaTool,
    FirecrawlTool,
    BatchArticleScraperTool,
)
from crewai_custom_tools.tools.web.wikipedia import (
    WikipediaSearchTool,
    WikipediaArticleTool,
)
from crewai_custom_tools.tools.web.rss import RssFeedParserTool, OpmlParserTool
from crewai_custom_tools.tools.web.fact_checking import GoogleFactCheckTool
from crewai_custom_tools.tools.web.search_providers import (
    BraveSearchTool,
    TavilyTool,
    SerpApiTool,
    HybridSearchTool,
)
from crewai_custom_tools.tools.web.perplexity_structured import PerplexityStructuredTool

# 2. Stocks & Market Data
from crewai_custom_tools.tools.finance.yfinance_ticker import YahooFinanceTickerInfoTool
from crewai_custom_tools.tools.finance.yfinance_news import YahooFinanceNewsTool
from crewai_custom_tools.tools.finance.company_info import YahooFinanceCompanyInfoTool
from crewai_custom_tools.tools.finance.history_holdings import (
    YahooFinanceETFHoldingsTool,
    YahooFinanceHistoryTool,
)
from crewai_custom_tools.tools.finance.crypto import (
    CoinMarketCapInfoTool,
    KrakenTickerInfoTool,
    KrakenAssetListTool,
)
from crewai_custom_tools.tools.finance.market_data import (
    FREDMacroTool,
    AlphaVantageOverviewTool,
)
from crewai_custom_tools.tools.finance.fear_greed import FearGreedTool
from crewai_custom_tools.tools.finance.exchange_rate import ExchangeRateTool
from crewai_custom_tools.tools.finance.coinmarketcap_extras import (
    CoinMarketCapListTool,
    CoinMarketCapNewsTool,
    CoinMarketCapHistoricalTool,
)
from crewai_custom_tools.tools.finance.enhanced import (
    TickerExistenceValidationTool,
    EnhancedETFAnalysisTool,
    EnhancedCryptoAnalysisTool,
    DeFiMetricsTool,
)
from crewai_custom_tools.tools.finance.indicators import (
    TwelveDataIndicatorTool,
    TwelveDataMultiIndicatorTool,
)
from crewai_custom_tools.tools.finance.market_extras import (
    AlphaVantageNewsSentimentTool,
    ChartImgTool,
)

# 3. OSINT & Cyber Recon
from crewai_custom_tools.tools.osint.github import GitHubSearchTool, GitHubOrgSearchTool
from crewai_custom_tools.tools.osint.email_recon import (
    HunterIOTool,
    SerperEmailSearchTool,
    EpieosEmailLookupTool,
    HoleheEmailScannerTool,
)
from crewai_custom_tools.tools.osint.person_recon import UsernameSearchTool
from crewai_custom_tools.tools.osint.domain_recon import CrtShTool, RDAPDomainTool
from crewai_custom_tools.tools.osint.registers import FrenchRegistryTool
from crewai_custom_tools.tools.osint.corporate_global import OpenCorporatesSearchTool

# 4. Reports & PDFs formatting
from crewai_custom_tools.reporting.html_generator import RenderReportTool, validate_html
from crewai_custom_tools.reporting.pdf_generator import HtmlToPdfTool
from crewai_custom_tools.reporting.template_renderers import (
    PestelReportRenderer,
    FinancialReportRenderer,
)

# 5. Workspace Enterprise integrations
from crewai_custom_tools.enterprise.todoist import TodoistTool
from crewai_custom_tools.enterprise.airtable import AirtableReaderTool, AirtableTool
from crewai_custom_tools.enterprise.accuweather import AccuWeatherTool
from crewai_custom_tools.enterprise.rag_tools import SaveToRagTool

__all__ = [
    # Web Tools
    "PerplexitySearchTool",
    "SerperSearchTool",
    "UnifiedScraperTool",
    "ScrapeNinjaTool",
    "FirecrawlTool",
    "BatchArticleScraperTool",
    "WikipediaSearchTool",
    "WikipediaArticleTool",
    "RssFeedParserTool",
    "OpmlParserTool",
    "GoogleFactCheckTool",
    "BraveSearchTool",
    "TavilyTool",
    "SerpApiTool",
    "HybridSearchTool",
    "PerplexityStructuredTool",
    # Finance Tools
    "YahooFinanceTickerInfoTool",
    "YahooFinanceNewsTool",
    "YahooFinanceCompanyInfoTool",
    "YahooFinanceETFHoldingsTool",
    "YahooFinanceHistoryTool",
    "CoinMarketCapInfoTool",
    "KrakenTickerInfoTool",
    "KrakenAssetListTool",
    "FREDMacroTool",
    "AlphaVantageOverviewTool",
    "FearGreedTool",
    "ExchangeRateTool",
    "CoinMarketCapListTool",
    "CoinMarketCapNewsTool",
    "CoinMarketCapHistoricalTool",
    "TickerExistenceValidationTool",
    "EnhancedETFAnalysisTool",
    "EnhancedCryptoAnalysisTool",
    "DeFiMetricsTool",
    "TwelveDataIndicatorTool",
    "TwelveDataMultiIndicatorTool",
    "AlphaVantageNewsSentimentTool",
    "ChartImgTool",
    # OSINT Tools
    "GitHubSearchTool",
    "GitHubOrgSearchTool",
    "HunterIOTool",
    "SerperEmailSearchTool",
    "EpieosEmailLookupTool",
    "HoleheEmailScannerTool",
    "UsernameSearchTool",
    "CrtShTool",
    "RDAPDomainTool",
    "FrenchRegistryTool",
    "OpenCorporatesSearchTool",
    # Reporting Tools
    "validate_html",
    "RenderReportTool",
    "HtmlToPdfTool",
    "PestelReportRenderer",
    "FinancialReportRenderer",
    # Enterprise Tools
    "TodoistTool",
    "AirtableReaderTool",
    "AirtableTool",
    "AccuWeatherTool",
    "SaveToRagTool",
]
