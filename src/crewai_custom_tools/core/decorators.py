"""Resiliency and error handling decorators for API-backed tools."""

import logging
import concurrent.futures
from functools import wraps
from time import sleep
from typing import Any, Callable, Optional
import requests

logger = logging.getLogger("crewai_custom_tools.decorators")


def api_tool(
    provider: str, endpoint: str, timeout: float = 30.0, default_return: Any = None
) -> Callable:
    """
    Decorator for API tools to provide consistent error handling, retrying, and rate limiting.

    Args:
        provider: The name of the API provider (e.g., 'Perplexity', 'Yahoo Finance')
        endpoint: The name/category of the endpoint being hit
        timeout: Request timeout value in seconds (default 30.0)
        default_return: Value to return in case of a terminal failure
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    logger.warning(
                        f"Function {func.__name__} timed out after {timeout}s"
                    )
                    return (
                        default_return
                        or f"Timeout error: Function timed out after {timeout}s"
                    )
            except requests.exceptions.HTTPError as e:
                # Intercept HTTP 429 and retry with sleep
                if e.response is not None and e.response.status_code == 429:
                    logger.warning(
                        f"Rate limited by {provider} {endpoint}. Retrying..."
                    )
                    sleep(2.0)
                    retry_executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=1
                    )
                    try:
                        retry_future = retry_executor.submit(func, *args, **kwargs)
                        return retry_future.result(timeout=timeout)
                    except concurrent.futures.TimeoutError:
                        logger.warning(
                            f"Function {func.__name__} retry timed out after {timeout}s"
                        )
                        return (
                            default_return
                            or f"Timeout error: Function timed out after {timeout}s"
                        )
                    except Exception as retry_err:
                        logger.error(
                            f"API Retry failed in {provider} {endpoint}: {retry_err}"
                        )
                    finally:
                        retry_executor.shutdown(wait=False)

                logger.error(f"API Error in {provider} {endpoint}: {e}")
                return default_return or f"Error calling {provider}: {e}"
            except Exception as e:
                logger.error(f"Execution failed in {provider} {endpoint}: {e}")
                return default_return or f"Unexpected failure: {e}"
            finally:
                executor.shutdown(wait=False)

        return wrapper

    return decorator
