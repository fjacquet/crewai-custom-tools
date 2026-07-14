"""Resiliency and error handling decorators for API-backed tools."""

import concurrent.futures
import logging
from functools import wraps
from time import sleep
from typing import Any, Callable

import requests

from crewai_custom_tools.core.rate_limiter import get_rate_limiter
from crewai_custom_tools.core.results import err

logger = logging.getLogger("crewai_custom_tools.decorators")


def _run_with_timeout(
    func: Callable, args: tuple, kwargs: dict, timeout: float
) -> Any:
    """Run ``func`` in a worker thread, raising ``TimeoutError`` past ``timeout``."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(func, *args, **kwargs).result(timeout=timeout)
    finally:
        # wait=False: a hung call cannot be cancelled, so we abandon the worker
        # rather than block. Tools MUST set their own per-request timeout to bound it.
        executor.shutdown(wait=False)


def api_tool(
    provider: str,
    endpoint: str,
    timeout: float = 30.0,
) -> Callable:
    """Wrap a tool ``_run`` with a timeout, a single HTTP-429 retry, and a JSON error envelope.

    On any failure the wrapper returns ``err("<provider> <endpoint>: <detail>")`` — a
    canonical ``{"success": false, "data": null, "error": ...}`` JSON string — so a caller
    can always distinguish a genuine failure from an empty-but-successful result.

    Args:
        provider: API provider name, used in log lines and the error message.
        endpoint: Endpoint/category name, used in log lines and the error message.
        timeout: Per-call wall-clock timeout in seconds.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                get_rate_limiter().acquire(provider)
                return _run_with_timeout(func, args, kwargs, timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(f"{provider} {endpoint} timed out after {timeout}s")
                return err(f"{provider} {endpoint}: timed out after {timeout}s")
            except requests.exceptions.HTTPError as e:
                if getattr(e.response, "status_code", None) == 429:
                    logger.warning(f"Rate limited by {provider} {endpoint}; retrying once")
                    sleep(2.0)
                    try:
                        get_rate_limiter().acquire(provider)
                        return _run_with_timeout(func, args, kwargs, timeout)
                    except Exception as retry_err:  # noqa: BLE001
                        logger.error(f"{provider} {endpoint} retry failed: {retry_err}")
                        return err(f"{provider} {endpoint}: {retry_err}")
                logger.error(f"{provider} {endpoint} HTTP error: {e}")
                return err(f"{provider} {endpoint}: {e}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"{provider} {endpoint} failed: {e}")
                return err(f"{provider} {endpoint}: {e}")

        return wrapper

    return decorator
