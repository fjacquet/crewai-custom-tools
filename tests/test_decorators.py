"""Tests for the api_tool decorator in crewai_custom_tools/core/decorators.py."""

import time
import pytest
import requests
import concurrent.futures
from unittest.mock import MagicMock
from crewai_custom_tools.core.decorators import api_tool


def test_api_tool_success():
    """Test that api_tool executes a successful function and returns its result."""

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def my_tool(x):
        return x + 1

    assert my_tool(5) == 6


def test_api_tool_timeout_non_blocking():
    """
    Test that api_tool handles timeouts and returns instantly on timeout without blocking.
    A slow function runs for 2.0s but has a timeout of 0.1s.
    The decorator should return the timeout message in ~0.1s, rather than waiting for 2.0s.
    """

    @api_tool(provider="TestProvider", endpoint="TestEndpoint", timeout=0.1)
    def slow_tool():
        time.sleep(1.0)
        return "slow_success"

    start_time = time.time()
    result = slow_tool()
    duration = time.time() - start_time

    assert "Timeout error" in result
    # It should have returned in significantly less than 1.0s (e.g., < 0.3s)
    assert duration < 0.4


def test_api_tool_default_return_on_timeout():
    """Test that api_tool returns the configured default_return value on timeout."""

    @api_tool(
        provider="TestProvider",
        endpoint="TestEndpoint",
        timeout=0.1,
        default_return="fallback_val",
    )
    def slow_tool():
        time.sleep(0.5)
        return "slow_success"

    result = slow_tool()
    assert result == "fallback_val"


def test_api_tool_http_429_retry_success(mocker):
    """Test that api_tool retries on HTTP 429 status code and succeeds if the retry succeeds."""
    # Mock sleep so we don't actually wait 2.0s in the test
    mock_sleep = mocker.patch("crewai_custom_tools.core.decorators.sleep")

    call_count = 0

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def rate_limited_tool():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            response = requests.Response()
            response.status_code = 429
            raise requests.exceptions.HTTPError("Rate limited", response=response)
        return "success_after_retry"

    result = rate_limited_tool()
    assert result == "success_after_retry"
    assert call_count == 2
    mock_sleep.assert_called_once_with(2.0)


def test_api_tool_http_429_retry_timeout(mocker):
    """Test that api_tool retries on HTTP 429, but if the retry times out, it handles it properly."""
    mocker.patch("crewai_custom_tools.core.decorators.sleep")

    call_count = 0

    @api_tool(provider="TestProvider", endpoint="TestEndpoint", timeout=0.1)
    def rate_limited_slow_tool():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            response = requests.Response()
            response.status_code = 429
            raise requests.exceptions.HTTPError("Rate limited", response=response)
        # Second call is slow and should timeout
        time.sleep(0.5)
        return "slow_success"

    result = rate_limited_slow_tool()
    assert "Timeout error" in result
    assert call_count == 2


def test_api_tool_other_http_error_no_retry():
    """Test that api_tool does not retry for other HTTP errors (e.g., 500 Internal Server Error)."""
    call_count = 0

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def http_error_tool():
        nonlocal call_count
        call_count += 1
        response = requests.Response()
        response.status_code = 500
        raise requests.exceptions.HTTPError("Internal Server Error", response=response)

    result = http_error_tool()
    assert "Error calling TestProvider" in result
    assert call_count == 1


def test_api_tool_unexpected_exception():
    """Test that api_tool handles unexpected exceptions gracefully."""

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def broken_tool():
        raise ValueError("Generic DB error")

    result = broken_tool()
    assert "Unexpected failure" in result
