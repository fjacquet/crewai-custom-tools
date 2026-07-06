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
]
