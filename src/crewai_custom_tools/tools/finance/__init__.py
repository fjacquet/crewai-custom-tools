"""Finance, Stock, Crypto, and Macroeconomic tools."""

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
from crewai_custom_tools.tools.finance.enhanced import (
    TickerExistenceValidationTool,
    EnhancedETFAnalysisTool,
    EnhancedCryptoAnalysisTool,
    DeFiMetricsTool,
)
from crewai_custom_tools.tools.finance.sec import EnhancedSECAnalysisTool
from crewai_custom_tools.tools.finance.risk import StandardizedRiskScoringTool
from crewai_custom_tools.tools.finance.sentiment import (
    StandardizedSentimentAnalysisTool,
    CrossAssetSentimentComparatorTool,
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

__all__ = [
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
    "TickerExistenceValidationTool",
    "EnhancedETFAnalysisTool",
    "EnhancedCryptoAnalysisTool",
    "DeFiMetricsTool",
    "EnhancedSECAnalysisTool",
    "StandardizedRiskScoringTool",
    "StandardizedSentimentAnalysisTool",
    "CrossAssetSentimentComparatorTool",
    "TwelveDataIndicatorTool",
    "TwelveDataMultiIndicatorTool",
    "AlphaVantageNewsSentimentTool",
    "ChartImgTool",
    "MarketScreeningTool",
]
