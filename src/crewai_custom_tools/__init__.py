"""Centralized CrewAI custom tools library."""

__version__ = "0.6.1"

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
from crewai_custom_tools.tools.web.places import GeoapifyPlacesTool
from crewai_custom_tools.tools.web.tech_stack import TechStackTool
from crewai_custom_tools.tools.web.wikipedia_processing import WikipediaProcessingTool
from crewai_custom_tools.tools.web.rss_aggregator import RSSFeedTool, UnifiedRssTool

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
from crewai_custom_tools.tools.finance.screening import MarketScreeningTool
from crewai_custom_tools.tools.finance.risk import StandardizedRiskScoringTool
from crewai_custom_tools.tools.finance.sec import EnhancedSECAnalysisTool
from crewai_custom_tools.tools.finance.sentiment import (
    StandardizedSentimentAnalysisTool,
    CrossAssetSentimentComparatorTool,
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
from crewai_custom_tools.tools.osint.registers_extra import InseeSireneTool, BodaccTool
from crewai_custom_tools.tools.osint.signals import GdeltTool, GoogleNewsRssTool
from crewai_custom_tools.tools.osint.hunter_extra import (
    HunterEmailFinderTool,
    HunterEmailVerifierTool,
)
from crewai_custom_tools.tools.osint.cli_providers import (
    SherlockTool,
    MaigretTool,
    TheHarvesterTool,
    NetReconTool,
)
from crewai_custom_tools.tools.osint.email_delegator import DelegatingEmailSearchTool

# 4. Reports & PDFs formatting
from crewai_custom_tools.reporting.html_generator import RenderReportTool, validate_html
from crewai_custom_tools.reporting.pdf_generator import HtmlToPdfTool
from crewai_custom_tools.reporting.template_renderers import (
    PestelReportRenderer,
    FinancialReportRenderer,
)
from crewai_custom_tools.reporting.report_writers import (
    ReportingTool,
    UniversalReportTool,
)
from crewai_custom_tools.reporting.data_centric import (
    MetricsCalculatorTool,
    KPITrackerTool,
    DataVisualizationTool,
    StructuredReportTool,
)
from crewai_custom_tools.reporting.html_builder import HtmlGeneratorTool

# 5. Workspace Enterprise integrations
from crewai_custom_tools.enterprise.todoist import TodoistTool
from crewai_custom_tools.enterprise.airtable import AirtableReaderTool, AirtableTool
from crewai_custom_tools.enterprise.accuweather import AccuWeatherTool
from crewai_custom_tools.enterprise.rag_tools import SaveToRagTool

# 6. Files
from crewai_custom_tools.tools.files import FileReadTool, DirectoryReadTool

# 7. Analytics (valuation, ETF, regulatory, position sizing, A+ grading/screening)
from crewai_custom_tools.tools.analytics import (
    ValuationTool,
    ETFAnalysisTool,
    RegulatoryComplianceTool,
    PositionSizingTool,
    PriceTargetCalculator,
    APlusScoringTool,
    APlusScreeningTool,
)

# 8. Core helpers (programmatic consumers)
from crewai_custom_tools.core.keys import require_api_key
from crewai_custom_tools.core.rate_limiter import get_rate_limiter
from crewai_custom_tools.core.results import ToolResultError, ok, err, parse_tool_result
from crewai_custom_tools.tools.web.perplexity_structured import perplexity_structured

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
    "GeoapifyPlacesTool",
    "TechStackTool",
    "WikipediaProcessingTool",
    "RSSFeedTool",
    "UnifiedRssTool",
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
    "MarketScreeningTool",
    "StandardizedRiskScoringTool",
    "EnhancedSECAnalysisTool",
    "TwelveDataIndicatorTool",
    "TwelveDataMultiIndicatorTool",
    "AlphaVantageNewsSentimentTool",
    "ChartImgTool",
    "StandardizedSentimentAnalysisTool",
    "CrossAssetSentimentComparatorTool",
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
    "InseeSireneTool",
    "BodaccTool",
    "GdeltTool",
    "GoogleNewsRssTool",
    "HunterEmailFinderTool",
    "HunterEmailVerifierTool",
    "DelegatingEmailSearchTool",
    "SherlockTool",
    "MaigretTool",
    "TheHarvesterTool",
    "NetReconTool",
    # Reporting Tools
    "validate_html",
    "RenderReportTool",
    "HtmlToPdfTool",
    "PestelReportRenderer",
    "FinancialReportRenderer",
    "ReportingTool",
    "UniversalReportTool",
    "MetricsCalculatorTool",
    "KPITrackerTool",
    "DataVisualizationTool",
    "StructuredReportTool",
    "HtmlGeneratorTool",
    # Enterprise Tools
    "TodoistTool",
    "AirtableReaderTool",
    "AirtableTool",
    "AccuWeatherTool",
    "SaveToRagTool",
    # File Tools
    "FileReadTool",
    "DirectoryReadTool",
    # Analytics Tools (plain classes noted: not BaseTool, so not on the MCP surface)
    "ValuationTool",
    "ETFAnalysisTool",
    "RegulatoryComplianceTool",
    "PositionSizingTool",  # plain class — programmatic API only
    "PriceTargetCalculator",  # plain class — programmatic API only
    "APlusScoringTool",
    "APlusScreeningTool",
    # Core helpers
    "require_api_key",
    "get_rate_limiter",
    "ToolResultError",
    "ok",
    "err",
    "parse_tool_result",
    "perplexity_structured",
]
