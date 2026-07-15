import logging
import time

import pytest

from crewai_custom_tools.core.rate_limiter import (
    DEFAULT_RATE_LIMITS,
    RateLimit,
    RateLimiterRegistry,
    RateLimitExceeded,
    get_rate_limiter,
    reset_rate_limiter,
)


@pytest.fixture(autouse=True)
def _enable_rate_limiting(monkeypatch):
    # The suite-wide conftest disables limiting; re-enable it for these tests.
    monkeypatch.delenv("CREWAI_TOOLS_RATE_LIMIT_DISABLED", raising=False)
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def test_burst_capacity_is_immediate():
    registry = RateLimiterRegistry({"Demo": RateLimit(requests_per_minute=6000, burst=3)})
    start = time.monotonic()
    for _ in range(3):
        registry.acquire("Demo")
    assert time.monotonic() - start < 0.05


def test_acquire_blocks_after_burst_exhausted():
    # 6000/min = 100 tokens/sec -> 4th call waits ~10ms
    registry = RateLimiterRegistry({"Demo": RateLimit(requests_per_minute=6000, burst=3)})
    for _ in range(3):
        registry.acquire("Demo")
    start = time.monotonic()
    registry.acquire("Demo")
    assert time.monotonic() - start >= 0.005


def test_unknown_provider_is_noop():
    registry = RateLimiterRegistry({})
    start = time.monotonic()
    for _ in range(100):
        registry.acquire("NeverConfigured")
    assert time.monotonic() - start < 0.05


def test_kill_switch_disables_limiting(monkeypatch):
    monkeypatch.setenv("CREWAI_TOOLS_RATE_LIMIT_DISABLED", "1")
    registry = RateLimiterRegistry({"Demo": RateLimit(requests_per_minute=1, burst=1)})
    start = time.monotonic()
    for _ in range(5):
        registry.acquire("Demo")
    assert time.monotonic() - start < 0.05


def test_premium_override_via_env(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_PREMIUM", "true")
    reset_rate_limiter()
    registry = get_rate_limiter()
    assert registry.limit_for("AlphaVantage") == RateLimit(requests_per_minute=75, burst=10)


def test_default_limits_cover_known_providers():
    for provider in ("YahooFinance", "Perplexity", "AlphaVantage", "TwelveData"):
        assert provider in DEFAULT_RATE_LIMITS


def test_get_rate_limiter_is_singleton():
    assert get_rate_limiter() is get_rate_limiter()


def test_acquire_raises_when_max_wait_exceeded():
    registry = RateLimiterRegistry({"Slow": RateLimit(requests_per_minute=1, burst=1)})
    registry.acquire("Slow")  # consumes the only burst token
    with pytest.raises(RateLimitExceeded, match="Slow"):
        registry.acquire("Slow", max_wait=0.05)


def test_acquire_env_default_max_wait(monkeypatch):
    monkeypatch.setenv("CREWAI_TOOLS_RATE_LIMIT_MAX_WAIT", "0.05")
    registry = RateLimiterRegistry({"Slow": RateLimit(requests_per_minute=1, burst=1)})
    registry.acquire("Slow")
    with pytest.raises(RateLimitExceeded):
        registry.acquire("Slow")


def test_long_wait_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr("crewai_custom_tools.core.rate_limiter._WARN_WAIT_SECONDS", 0.01)
    registry = RateLimiterRegistry({"Chatty": RateLimit(requests_per_minute=600, burst=1)})
    registry.acquire("Chatty")
    with caplog.at_level(logging.WARNING, logger="crewai_custom_tools.rate_limiter"):
        registry.acquire("Chatty")  # ~0.1s refill wait > 0.01 threshold
    assert any("Chatty" in rec.message for rec in caplog.records)


def test_new_providers_registered():
    for provider in ("TickerValidation", "CoinGecko", "DeFiLlama"):
        assert provider in DEFAULT_RATE_LIMITS
