"""Enhanced finance analysis tools: ETF, crypto, DeFi, and ticker validation.

Ported from finwiz but rewritten to use only REAL data sources (yfinance funds_data,
CoinGecko, DeFiLlama, Coinbase) — the finwiz originals fell back to fabricated
"sample" holdings / hardcoded TVL, which this library deliberately avoids: an
honest error beats a made-up number.
"""

from typing import Any, Literal, Optional

import requests
import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

# ---------------------------------------------------------------------------
# Ticker existence validation
# ---------------------------------------------------------------------------

_COINBASE_PRODUCTS = "https://api.exchange.coinbase.com/products"
_EQUITY_TYPES = {"EQUITY", "COMMONSTOCK", "PREFERREDSTOCK"}
AssetClass = Literal["stock", "etf", "crypto", "auto"]


class TickerValidationInput(BaseModel):
    """Input schema for TickerExistenceValidationTool."""

    symbol: str = Field(..., description="The ticker/symbol to validate (e.g. AAPL, VOO, BTC).")
    asset_class: str = Field(
        "auto", description="One of 'stock', 'etf', 'crypto', or 'auto' (detect)."
    )


class TickerExistenceValidationTool(BaseTool):
    """Validate that a ticker exists on Yahoo Finance (equities/ETFs) or Coinbase (crypto)."""

    name: str = "ticker_existence_validation"
    description: str = (
        "Validate that a ticker exists and classify its asset class: equities/ETFs via "
        "Yahoo Finance, crypto via Coinbase. Returns {symbol, asset_class, valid, reason, meta}."
    )
    args_schema: type[BaseModel] = TickerValidationInput

    @api_tool(provider="TickerValidation", endpoint="Validate")
    def _run(self, symbol: str, asset_class: str = "auto") -> str:
        if asset_class == "crypto":
            return ok(self._validate_crypto(symbol))
        result = self._validate_yahoo(symbol, asset_class)
        if result["reason"] == "unknown_quote_type_try_crypto":
            return ok(self._validate_crypto(symbol))
        return ok(result)

    @staticmethod
    def _validate_yahoo(symbol: str, asset_class: str) -> dict[str, Any]:
        info = yf.Ticker(symbol).info or {}
        if not info:
            return {
                "symbol": symbol,
                "asset_class": asset_class,
                "valid": False,
                "reason": "not_found_on_yahoo",
                "meta": {"source": "yahoo"},
            }
        quote_type = (info.get("quoteType") or "").upper()
        exchange = (info.get("exchange") or "").upper()
        detected = asset_class
        if asset_class == "auto":
            if quote_type == "ETF":
                detected = "etf"
            elif quote_type in _EQUITY_TYPES:
                detected = "stock"
            else:
                return {
                    "symbol": symbol,
                    "asset_class": "auto",
                    "valid": False,
                    "reason": "unknown_quote_type_try_crypto",
                    "meta": {"source": "yahoo", "quoteType": quote_type},
                }
        valid = (quote_type == "ETF") if detected == "etf" else (quote_type in _EQUITY_TYPES)
        valid = bool(valid and exchange)
        return {
            "symbol": symbol,
            "asset_class": detected,
            "valid": valid,
            "reason": None if valid else "invalid_or_unknown_exchange",
            "meta": {
                "exchange": exchange,
                "currency": info.get("currency") or "",
                "name": info.get("longName") or info.get("shortName") or "",
                "quoteType": quote_type,
                "source": "yahoo",
            },
        }

    @staticmethod
    def _validate_crypto(symbol: str) -> dict[str, Any]:
        sym = symbol.upper()
        resp = requests.get(_COINBASE_PRODUCTS, timeout=10)
        resp.raise_for_status()
        pairs = [p.get("id") for p in resp.json() if isinstance(p.get("id"), str)]
        matching = [pid for pid in pairs if pid == sym or pid.startswith(f"{sym}-")]
        exists = bool(matching)
        return {
            "symbol": sym,
            "asset_class": "crypto",
            "valid": exists,
            "reason": None if exists else "not_listed_on_coinbase",
            "meta": {"pairs": matching[:10], "source": "coinbase"},
        }


# ---------------------------------------------------------------------------
# Enhanced ETF analysis (real funds_data + concentration risk)
# ---------------------------------------------------------------------------


class EnhancedETFAnalysisInput(BaseModel):
    """Input schema for EnhancedETFAnalysisTool."""

    ticker: str = Field(..., description="ETF ticker symbol (e.g. SPY, QQQ, VOO).")
    max_holdings: int = Field(10, description="Maximum number of top holdings to return.")


def _concentration_level(top_weight_pct: float | None) -> str | None:
    """Classify how concentrated an ETF's top holdings are (percent of assets)."""
    if top_weight_pct is None:
        return None
    if top_weight_pct >= 60:
        return "high"
    if top_weight_pct >= 35:
        return "moderate"
    return "low"


class EnhancedETFAnalysisTool(BaseTool):
    """Analyze an ETF's real holdings, sector mix, expense ratio, and concentration risk."""

    name: str = "enhanced_etf_analysis"
    description: str = (
        "Comprehensive ETF analysis from Yahoo Finance funds data: top holdings, sector "
        "weightings, expense ratio, AUM, and a concentration-risk assessment (top-N weight + HHI)."
    )
    args_schema: type[BaseModel] = EnhancedETFAnalysisInput

    @api_tool(provider="YahooFinance", endpoint="EnhancedETF")
    def _run(self, ticker: str, max_holdings: int = 10) -> str:
        etf = yf.Ticker(ticker.upper())
        info = etf.info or {}

        holdings: list[dict] = []
        sector_weightings: dict[str, float] = {}
        try:
            funds = etf.get_funds_data()
            top = funds.top_holdings
            if top is not None and not top.empty:
                for symbol, row in top.head(max_holdings).iterrows():
                    holdings.append(
                        {"symbol": str(symbol), "name": str(row.get("Name")), "weight": row.get("Holding Percent")}
                    )
            weights = funds.sector_weightings
            if isinstance(weights, dict):
                sector_weightings = {k: float(v) for k, v in weights.items()}
        except Exception:
            pass

        if not holdings and not info:
            return err(f"No ETF data available for {ticker}")

        # Normalise weights to percent (funds_data returns fractions like 0.072).
        raw = [h["weight"] for h in holdings if isinstance(h["weight"], (int, float))]
        if raw and max(raw) <= 1.5:
            for h in holdings:
                if isinstance(h["weight"], (int, float)):
                    h["weight"] = round(h["weight"] * 100, 2)
        pct = [h["weight"] for h in holdings if isinstance(h["weight"], (int, float))]
        top_weight = round(sum(pct), 2) if pct else None
        hhi = round(sum(w * w for w in pct), 1) if pct else None

        return ok(
            {
                "ticker": ticker.upper(),
                "name": info.get("shortName") or info.get("longName"),
                "category": info.get("categoryName"),
                "expense_ratio": info.get("annualReportExpenseRatio") or info.get("netExpenseRatio"),
                "aum": info.get("totalAssets"),
                "top_holdings": holdings,
                "sector_weightings": sector_weightings,
                "concentration": {
                    "top_n_weight_pct": top_weight,
                    "hhi": hhi,
                    "risk_level": _concentration_level(top_weight),
                },
            }
        )


# ---------------------------------------------------------------------------
# Enhanced crypto analysis (real CoinGecko data + derived thesis/risk)
# ---------------------------------------------------------------------------

_COINGECKO = "https://api.coingecko.com/api/v3"
_COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "ADA": "cardano",
    "DOT": "polkadot",
    "SOL": "solana",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "XRP": "ripple",
    "DOGE": "dogecoin",
}


class EnhancedCryptoAnalysisInput(BaseModel):
    """Input schema for EnhancedCryptoAnalysisTool."""

    symbol: str = Field(..., description="Cryptocurrency symbol (e.g. BTC, ETH, SOL).")
    max_thesis_bullets: int = Field(8, description="Maximum number of thesis bullets.")


def _crypto_thesis(data: dict[str, Any], max_bullets: int) -> list[str]:
    """Build transparent, data-derived thesis bullets (no fabricated numbers)."""
    name = data.get("name", data["symbol"])
    rank = data.get("market_cap_rank") or 999
    cats = data.get("categories", [])
    bullets = []
    if rank <= 10:
        bullets.append(f"{name} is a top-10 asset by market cap — strong liquidity and acceptance.")
    elif rank <= 50:
        bullets.append(f"{name} sits in the top 50 by market cap — established market presence.")
    else:
        bullets.append(f"{name} is outside the top 50 — higher-risk, higher-potential positioning.")
    if any("smart contract" in str(c).lower() for c in cats):
        bullets.append("Smart-contract platform enabling a DeFi/dApp ecosystem.")
    if data.get("max_supply"):
        bullets.append(f"Capped max supply ({data['max_supply']:,.0f}) creates scarcity pressure.")
    if (data.get("price_change_7d") or 0) > 10:
        bullets.append("Strong 7-day momentum signals positive near-term sentiment.")
    if data["symbol"] in {"BTC", "ETH"}:
        bullets.append("Broad institutional adoption and integration into traditional products.")
    return bullets[:max_bullets]


def _crypto_risk(data: dict[str, Any]) -> dict[str, Any]:
    """Derive a 0-5 risk score from real market data (transparent factors)."""
    factors, score = [], 2.0
    rank = data.get("market_cap_rank") or 999
    if rank > 100:
        factors.append("Low market cap — elevated volatility/liquidity risk.")
        score += 1.0
    elif rank <= 10:
        factors.append("Large-cap with established liquidity.")
        score -= 0.3
    if abs(data.get("price_change_24h") or 0) > 15:
        factors.append("Extreme 24h volatility.")
        score += 1.0
    if not data.get("max_supply") and (data.get("total_supply") or 0) > 0:
        factors.append("Uncapped supply — inflation risk.")
        score += 0.4
    factors.append("General crypto regulatory and security risk.")
    score += 0.5
    score = max(0.0, min(score, 5.0))
    level = "Low" if score <= 1.5 else "Medium" if score <= 2.5 else "High" if score <= 4 else "Very High"
    return {"scale": "0_5", "score": round(score, 1), "level": level, "risk_factors": factors}


class EnhancedCryptoAnalysisTool(BaseTool):
    """Analyze a cryptocurrency from real CoinGecko data with a derived thesis and risk score."""

    name: str = "enhanced_crypto_analysis"
    description: str = (
        "Comprehensive crypto analysis from CoinGecko: market data, a data-derived "
        "investment thesis, and a 0-5 risk assessment with transparent factors."
    )
    args_schema: type[BaseModel] = EnhancedCryptoAnalysisInput

    @api_tool(provider="CoinGecko", endpoint="CoinData")
    def _run(self, symbol: str, max_thesis_bullets: int = 8) -> str:
        sym = symbol.upper()
        coin_id = _COINGECKO_IDS.get(sym, sym.lower())
        resp = requests.get(f"{_COINGECKO}/coins/{coin_id}", timeout=20)
        if resp.status_code == 404:
            return err(f"Cryptocurrency '{symbol}' not found on CoinGecko")
        resp.raise_for_status()
        raw = resp.json()
        market = raw.get("market_data", {})
        data = {
            "symbol": sym,
            "name": raw.get("name", "Unknown"),
            "current_price_usd": market.get("current_price", {}).get("usd"),
            "market_cap_usd": market.get("market_cap", {}).get("usd"),
            "volume_24h": market.get("total_volume", {}).get("usd"),
            "market_cap_rank": market.get("market_cap_rank"),
            "price_change_24h": market.get("price_change_percentage_24h"),
            "price_change_7d": market.get("price_change_percentage_7d"),
            "price_change_30d": market.get("price_change_percentage_30d"),
            "circulating_supply": market.get("circulating_supply"),
            "total_supply": market.get("total_supply"),
            "max_supply": market.get("max_supply"),
            "categories": [c for c in raw.get("categories", []) if c],
        }
        return ok(
            {
                "symbol": sym,
                "crypto_data": data,
                "investment_thesis": _crypto_thesis(data, max_thesis_bullets),
                "risk_assessment": _crypto_risk(data),
                "source": "CoinGecko",
            }
        )


# ---------------------------------------------------------------------------
# DeFi metrics (real DeFiLlama TVL, keyless)
# ---------------------------------------------------------------------------

_DEFILLAMA = "https://api.llama.fi"
_DEFI_SLUGS = {
    "UNI": "uniswap",
    "AAVE": "aave",
    "COMP": "compound-finance",
    "MKR": "makerdao",
    "SNX": "synthetix",
    "YFI": "yearn-finance",
    "SUSHI": "sushi",
    "CRV": "curve-dex",
    "BAL": "balancer",
    "LDO": "lido",
    "CAKE": "pancakeswap",
}


class DeFiMetricsInput(BaseModel):
    """Input schema for DeFiMetricsTool."""

    symbol: str = Field(..., description="DeFi protocol token symbol (e.g. UNI, AAVE, CRV).")


def _tvl_tier(tvl: float | None) -> str | None:
    """Bucket a protocol by real TVL size."""
    if not tvl:
        return None
    if tvl > 1e10:
        return "mega (>$10B)"
    if tvl > 1e9:
        return "large (>$1B)"
    if tvl > 1e8:
        return "medium (>$100M)"
    return "small (<$100M)"


def _defi_risk_factors(category: str | None, tvl: float | None) -> list[str]:
    """Transparent, category/TVL-based risk factors (no fabricated numbers)."""
    factors = ["Smart-contract vulnerability / exploit risk", "DeFi regulatory uncertainty"]
    cat = (category or "").lower()
    if "dex" in cat:
        factors.append("Impermanent loss and MEV extraction risk for LPs")
    elif "lending" in cat:
        factors.append("Liquidation and bad-debt risk during volatility")
    elif "stablecoin" in cat or "cdp" in cat:
        factors.append("Depeg and collateral-stability risk")
    if tvl is not None and tvl < 1e8:
        factors.append("Limited protocol maturity / battle-testing (small TVL)")
    return factors


class DeFiMetricsTool(BaseTool):
    """Fetch a DeFi protocol's real TVL and derived risk profile from DeFiLlama (keyless)."""

    name: str = "defi_metrics"
    description: str = (
        "Analyze a DeFi protocol using DeFiLlama's keyless API: real current TVL, chains, "
        "category, a TVL tier, and transparent DeFi-specific risk factors."
    )
    args_schema: type[BaseModel] = DeFiMetricsInput

    @api_tool(provider="DeFiLlama", endpoint="Protocol")
    def _run(self, symbol: str) -> str:
        slug = _DEFI_SLUGS.get(symbol.upper(), symbol.lower())
        resp = requests.get(f"{_DEFILLAMA}/protocol/{slug}", timeout=15)
        if resp.status_code == 404:
            return err(f"DeFi protocol not found on DeFiLlama for '{symbol}' (slug '{slug}')")
        resp.raise_for_status()
        data = resp.json()

        tvl_series = data.get("tvl") or []
        current_tvl = tvl_series[-1].get("totalLiquidityUSD") if tvl_series else None
        if current_tvl is None:
            chain_tvls = data.get("currentChainTvls") or {}
            current_tvl = sum(v for v in chain_tvls.values() if isinstance(v, (int, float))) or None

        category = data.get("category")
        return ok(
            {
                "symbol": symbol.upper(),
                "protocol": data.get("name"),
                "slug": slug,
                "category": category,
                "chains": data.get("chains", []),
                "current_tvl_usd": current_tvl,
                "tvl_tier": _tvl_tier(current_tvl),
                "risk_factors": _defi_risk_factors(category, current_tvl),
                "source": "DeFiLlama",
            }
        )
