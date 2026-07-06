"""Cryptocurrency Tools: CoinMarketCap & Kraken Exchange."""

import json
import logging
import os
import requests
import base64
import hashlib
import hmac
import time
import urllib.parse
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


from crewai_custom_tools.models import (
    CoinInfoInput,
    KrakenTickerInfoInput,
    KrakenAssetListInput,
)


class CoinMarketCapInfoTool(BaseTool):
    """Get detailed cryptocurrency information from CoinMarketCap."""

    name: str = "CoinMarketCap Cryptocurrency Info"
    description: str = (
        "Get detailed information about a specific cryptocurrency including price, "
        "market cap, volume, circulating supply, and other key metrics. "
        "Provide the cryptocurrency symbol (e.g., BTC, ETH, SOL)."
    )
    args_schema: type[BaseModel] = CoinInfoInput

    @api_tool(provider="CoinMarketCap", endpoint="Quotes", default_return="{}")
    def _run(self, symbol: str) -> str:
        """Retrieve detailed info about a coin."""
        api_key = os.environ.get("X-CMC_PRO_API_KEY") or os.environ.get(
            "COINMARKETCAP_API_KEY"
        )
        if not api_key:
            return json.dumps({"error": "CoinMarketCap API key not configured"})

        headers = {
            "X-CMC_PRO_API_KEY": api_key,
            "Accept": "application/json",
        }
        params = {"symbol": symbol.upper(), "convert": "USD"}
        response = requests.get(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if "data" not in data or symbol.upper() not in data["data"]:
            return json.dumps({"error": f"No data found for symbol: {symbol}"})

        crypto_data = data["data"][symbol.upper()]
        quote = crypto_data["quote"]["USD"]

        info_dict = {
            "name": crypto_data.get("name"),
            "symbol": crypto_data.get("symbol"),
            "price_usd": quote.get("price"),
            "market_cap_usd": quote.get("market_cap"),
            "volume_24h_usd": quote.get("volume_24h"),
            "percent_change_24h": quote.get("percent_change_24h"),
            "percent_change_7d": quote.get("percent_change_7d"),
            "circulating_supply": crypto_data.get("circulating_supply"),
            "max_supply": crypto_data.get("max_supply"),
            "cmc_rank": crypto_data.get("cmc_rank"),
            "last_updated": quote.get("last_updated"),
            "platform": crypto_data.get("platform", {}).get("name")
            if crypto_data.get("platform")
            else None,
            "tags": crypto_data.get("tags", [])[:5],
        }
        return json.dumps(info_dict)


class KrakenTickerInfoTool(BaseTool):
    """Get real-time ticker information from Kraken."""

    name: str = "Kraken Ticker Information"
    description: str = "Fetches real-time ticker information for a specific cryptocurrency pair from Kraken."
    args_schema: type[BaseModel] = KrakenTickerInfoInput

    @api_tool(provider="Kraken", endpoint="Ticker", default_return="{}")
    def _run(self, pair: str) -> str:
        """Fetch ticker pair data."""
        url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            return f"Error from Kraken API: {data['error']}"

        result_pair = list(data.get("result", {}).keys())
        if not result_pair:
            return f"No data found for pair {pair}. Invalid pair."

        ticker_data = data["result"][result_pair[0]]
        return json.dumps(ticker_data)


class KrakenAssetListTool(BaseTool):
    """Get account asset balances from Kraken exchange."""

    name: str = "Kraken Asset List"
    description: str = "Fetches your account's asset balances from Kraken, including asset names and quantities."
    args_schema: type[BaseModel] = KrakenAssetListInput

    def _get_kraken_signature(self, urlpath: str, data: dict, secret: str) -> str:
        """Create authentication signature for Kraken private endpoints."""
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())
        return sigdigest.decode()

    @api_tool(provider="Kraken", endpoint="Balance", default_return="[]")
    def _run(self, asset_class: str = "currency") -> str:
        """Execute private balance lookup."""
        api_key = os.environ.get("KRAKEN_API_KEY")
        api_secret = os.environ.get("KRAKEN_API_SECRET")

        if not api_key or not api_secret:
            return "Error: Kraken API credentials not configured in environment."

        url = "https://api.kraken.com/0/private/Balance"
        urlpath = "/0/private/Balance"
        data = {"nonce": str(int(time.time() * 1000)), "asset": asset_class}

        headers = {
            "API-Key": api_key,
            "API-Sign": self._get_kraken_signature(urlpath, data, api_secret),
        }

        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("error"):
            return f"Error from Kraken API: {result['error']}"

        assets = result.get("result", {})
        formatted_assets = []

        for asset_code, quantity in assets.items():
            try:
                qty = float(quantity)
                if qty <= 0:
                    continue
                formatted_assets.append({"asset": asset_code, "quantity": qty})
            except (ValueError, TypeError):
                formatted_assets.append({"asset": asset_code, "quantity": quantity})

        return json.dumps(formatted_assets)
