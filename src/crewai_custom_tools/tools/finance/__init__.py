"""Finance, Stock, Crypto, and Macroeconomic tools."""

from crewai_custom_tools.tools.finance.company_info import YahooFinanceCompanyInfoTool
from crewai_custom_tools.tools.finance.crypto import (
    CoinMarketCapInfoTool,
    KrakenAssetListTool,
    KrakenTickerInfoTool,
)
from crewai_custom_tools.tools.finance.enhanced import (
    DeFiMetricsTool,
    EnhancedCryptoAnalysisTool,
    EnhancedETFAnalysisTool,
    TickerExistenceValidationTool,
)
from crewai_custom_tools.tools.finance.exchange_rate import ExchangeRateTool
from crewai_custom_tools.tools.finance.fear_greed import FearGreedTool
from crewai_custom_tools.tools.finance.history_holdings import (
    YahooFinanceETFHoldingsTool,
    YahooFinanceHistoryTool,
)
from crewai_custom_tools.tools.finance.indicators import (
    TwelveDataIndicatorTool,
    TwelveDataMultiIndicatorTool,
)
from crewai_custom_tools.tools.finance.market_data import (
    AlphaVantageOverviewTool,
    FREDMacroTool,
)
from crewai_custom_tools.tools.finance.market_extras import (
    AlphaVantageNewsSentimentTool,
    ChartImgTool,
)
from crewai_custom_tools.tools.finance.risk import StandardizedRiskScoringTool
from crewai_custom_tools.tools.finance.screening import MarketScreeningTool
from crewai_custom_tools.tools.finance.sec import EnhancedSECAnalysisTool
from crewai_custom_tools.tools.finance.sentiment import (
    CrossAssetSentimentComparatorTool,
    StandardizedSentimentAnalysisTool,
)
from crewai_custom_tools.tools.finance.yfinance_news import YahooFinanceNewsTool
from crewai_custom_tools.tools.finance.yfinance_ticker import YahooFinanceTickerInfoTool

__all__ = [
    "AlphaVantageNewsSentimentTool",
    "AlphaVantageOverviewTool",
    "ChartImgTool",
    "CoinMarketCapInfoTool",
    "CrossAssetSentimentComparatorTool",
    "DeFiMetricsTool",
    "EnhancedCryptoAnalysisTool",
    "EnhancedETFAnalysisTool",
    "EnhancedSECAnalysisTool",
    "ExchangeRateTool",
    "FREDMacroTool",
    "FearGreedTool",
    "KrakenAssetListTool",
    "KrakenTickerInfoTool",
    "MarketScreeningTool",
    "StandardizedRiskScoringTool",
    "StandardizedSentimentAnalysisTool",
    "TickerExistenceValidationTool",
    "TwelveDataIndicatorTool",
    "TwelveDataMultiIndicatorTool",
    "YahooFinanceCompanyInfoTool",
    "YahooFinanceETFHoldingsTool",
    "YahooFinanceHistoryTool",
    "YahooFinanceNewsTool",
    "YahooFinanceTickerInfoTool",
]
