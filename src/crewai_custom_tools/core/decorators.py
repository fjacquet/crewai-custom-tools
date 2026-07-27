"""Resiliency and error handling decorators for API-backed tools."""

import concurrent.futures
import logging
from collections.abc import Callable
from functools import wraps
from time import sleep
from typing import Any

import requests

from crewai_custom_tools.core.rate_limiter import RateLimitExceeded, get_rate_limiter
from crewai_custom_tools.core.results import err

logger = logging.getLogger("crewai_custom_tools.decorators")

# Une reprise unique à 2 s ne survit à aucun étranglement réel : mesuré sur
# upload.wikimedia.org, l'avertissement et l'échec tombaient à deux secondes d'intervalle
# et TOUTES les images d'un run échouaient. Les pauses croissent pour laisser au quota le
# temps de se reconstituer.
_PAUSES_429 = (5.0, 20.0, 60.0)
_PAUSE_429_MAX = 120.0


def _pause_429(exc: Exception, defaut: float) -> float:
    """Pause avant de retenter : `Retry-After` s'il est lisible, sinon `defaut`.

    L'en-tête admet aussi une date HTTP. On ne la parse pas : un format inattendu doit
    retomber sur la pause prévue, jamais immobiliser l'appel sur une valeur devinée.
    Bornée par `_PAUSE_429_MAX` — un serveur qui réclame une journée ne doit pas figer
    l'outil pour une journée.
    """
    entetes = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        demande = float(entetes.get("Retry-After", ""))
    except (TypeError, ValueError):
        return defaut
    return min(demande, _PAUSE_429_MAX) if demande > 0 else defaut


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
    """Wrap a tool ``_run`` with a timeout, escalating HTTP-429 retries, and a JSON error envelope.

    A 429 is retried up to ``len(_PAUSES_429)`` times, honouring ``Retry-After`` when the
    server sends it. Any other status fails at once — insisting on a 404 only sleeps.

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
            except RateLimitExceeded as e:
                logger.warning(f"{provider} {endpoint} rate-limit budget exhausted: {e}")
                return err(f"{provider} {endpoint}: {e}")
            except requests.exceptions.HTTPError as e:
                if getattr(e.response, "status_code", None) != 429:
                    logger.error(f"{provider} {endpoint} HTTP error: {e}")
                    return err(f"{provider} {endpoint}: {e}")
                derniere: Exception = e
                for numero, defaut in enumerate(_PAUSES_429, start=1):
                    pause = _pause_429(derniere, defaut)
                    logger.warning(
                        f"Rate limited by {provider} {endpoint}; "
                        f"retry {numero}/{len(_PAUSES_429)} in {pause:g}s"
                    )
                    sleep(pause)
                    try:
                        get_rate_limiter().acquire(provider)
                        return _run_with_timeout(func, args, kwargs, timeout)
                    except requests.exceptions.HTTPError as retry_err:
                        derniere = retry_err
                        # Un autre code que 429 n'est plus un étranglement : insister
                        # ferait dormir l'outil sur une erreur qui ne passera jamais.
                        if getattr(retry_err.response, "status_code", None) != 429:
                            break
                    except Exception as retry_err:
                        derniere = retry_err
                        break
                logger.error(f"{provider} {endpoint} retry failed: {derniere}")
                return err(f"{provider} {endpoint}: {derniere}")
            except Exception as e:
                logger.error(f"{provider} {endpoint} failed: {e}")
                return err(f"{provider} {endpoint}: {e}")

        return wrapper

    return decorator
