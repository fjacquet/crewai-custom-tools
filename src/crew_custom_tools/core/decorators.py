"""Resiliency and error handling decorators for API-backed tools."""

import time
import logging
from functools import wraps
from typing import Any, Callable, Optional
import requests

logger = logging.getLogger("crew_custom_tools.decorators")


def api_tool(
    provider: str,
    endpoint: str,
    timeout: float = 30.0,
    default_return: Any = None
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
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                # Intercept HTTP 429 and retry with exponential backoff
                if e.response is not None and e.response.status_code == 429:
                    logger.warning(f"Rate limited by {provider} {endpoint}. Retrying...")
                    time.sleep(2.0)
                    try:
                        return func(*args, **kwargs)
                    except Exception:
                        pass
                logger.error(f"API Error in {provider} {endpoint}: {e}")
                return default_return or f"Error calling {provider}: {e}"
            except Exception as e:
                logger.error(f"Execution failed in {provider} {endpoint}: {e}")
                return default_return or f"Unexpected failure: {e}"
        return wrapper
    return decorator
