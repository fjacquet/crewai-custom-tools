"""Provider-keyed synchronous rate limiting for API-backed tools.

Ported from finwiz's async aiolimiter-based limiter and reduced to what the
sync ``@api_tool`` wrapper needs: a token bucket per provider, blocking
``acquire``. Providers are the same strings tools pass to ``@api_tool``.
Set ``CREWAI_TOOLS_RATE_LIMIT_DISABLED=1`` to bypass entirely (tests, CI).
"""

import logging
import os
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger("crewai_custom_tools.rate_limiter")

_WARN_WAIT_SECONDS = 5.0
_DEFAULT_MAX_WAIT = 120.0


class RateLimitExceeded(RuntimeError):
    """Raised when acquiring a token would exceed the caller's max_wait budget."""


@dataclass(frozen=True)
class RateLimit:
    """Token-bucket parameters for one provider."""

    requests_per_minute: int
    burst: int = 5


# Values ported from finwiz infrastructure/resilience/rate_limiter_config.py
DEFAULT_RATE_LIMITS: dict[str, RateLimit] = {
    "AlphaVantage": RateLimit(requests_per_minute=5, burst=2),
    "YahooFinance": RateLimit(requests_per_minute=600, burst=20),
    "TwelveData": RateLimit(requests_per_minute=8, burst=3),
    "ChartImg": RateLimit(requests_per_minute=30, burst=5),
    "CoinMarketCap": RateLimit(requests_per_minute=30, burst=5),
    "Kraken": RateLimit(requests_per_minute=60, burst=10),
    "SECEdgar": RateLimit(requests_per_minute=10, burst=3),
    "Perplexity": RateLimit(requests_per_minute=30, burst=5),
    "FRED": RateLimit(requests_per_minute=120, burst=20),
    "FearGreed": RateLimit(requests_per_minute=10, burst=2),
    "TickerValidation": RateLimit(requests_per_minute=120, burst=10),
    "CoinGecko": RateLimit(requests_per_minute=30, burst=5),
    "DeFiLlama": RateLimit(requests_per_minute=60, burst=10),
    # Genealogy geo resolvers (crewai_custom_tools/tools/genealogy/geo/*)
    "Nominatim": RateLimit(requests_per_minute=60, burst=1),   # ODbL: max 1 req/s, no burst
    "Swisstopo": RateLimit(requests_per_minute=600, burst=10),  # ~10 req/s, conservative
    "GeoApiGouvFr": RateLimit(requests_per_minute=600, burst=10),  # ~10 req/s, conservative
}

# env var -> (provider, premium limit); mirrors finwiz's premium-tier switches
_PREMIUM_OVERRIDES: dict[str, tuple[str, RateLimit]] = {
    "ALPHA_VANTAGE_PREMIUM": ("AlphaVantage", RateLimit(requests_per_minute=75, burst=10)),
    "TWELVE_DATA_PREMIUM": ("TwelveData", RateLimit(requests_per_minute=800, burst=50)),
}


class _TokenBucket:
    def __init__(self, limit: RateLimit) -> None:
        self._capacity = float(limit.burst)
        self._tokens = float(limit.burst)
        self._refill_per_sec = limit.requests_per_minute / 60.0
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, provider: str, max_wait: float | None = None) -> None:
        deadline = None if max_wait is None else time.monotonic() + max_wait
        waited = 0.0
        warned = False
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self._capacity, self._tokens + (now - self._updated) * self._refill_per_sec)
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._refill_per_sec
            if deadline is not None and time.monotonic() + wait > deadline:
                raise RateLimitExceeded(f"{provider}: rate-limit wait would exceed {max_wait:.1f}s (waited {waited:.1f}s)")
            if not warned and waited + wait > _WARN_WAIT_SECONDS:
                logger.warning(f"{provider}: rate-limited, waiting {wait:.1f}s for a token (total wait so far {waited:.1f}s)")
                warned = True
            time.sleep(wait)
            waited += wait


class RateLimiterRegistry:
    """Per-provider token buckets. Unknown providers pass through unthrottled."""

    def __init__(self, limits: dict[str, RateLimit] | None = None) -> None:
        base = dict(DEFAULT_RATE_LIMITS if limits is None else limits)
        for env_var, (provider, premium) in _PREMIUM_OVERRIDES.items():
            if provider in base and os.getenv(env_var, "false").lower() == "true":
                base[provider] = premium
        self._limits = base
        self._buckets = {provider: _TokenBucket(limit) for provider, limit in base.items()}

    def limit_for(self, provider: str) -> RateLimit | None:
        return self._limits.get(provider)

    def acquire(self, provider: str, max_wait: float | None = None) -> None:
        if os.getenv("CREWAI_TOOLS_RATE_LIMIT_DISABLED", "").lower() in ("1", "true"):
            return
        bucket = self._buckets.get(provider)
        if bucket is None:
            return
        if max_wait is None:
            max_wait = float(os.getenv("CREWAI_TOOLS_RATE_LIMIT_MAX_WAIT", str(_DEFAULT_MAX_WAIT)))
        bucket.acquire(provider, max_wait)


_registry: RateLimiterRegistry | None = None
_registry_lock = threading.Lock()


def get_rate_limiter() -> RateLimiterRegistry:
    """Return the process-wide registry, creating it on first use."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = RateLimiterRegistry()
    return _registry


def reset_rate_limiter() -> None:
    """Discard the singleton (tests only — premium env vars are read at creation)."""
    global _registry
    _registry = None
