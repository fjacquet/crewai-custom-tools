"""Tests for the api_tool decorator in crewai_custom_tools/core/decorators.py."""

import json
import time

import requests

from crewai_custom_tools.core.decorators import api_tool


def _envelope(result):
    """Parse a tool result and assert it is a canonical envelope; return the dict."""
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


def test_api_tool_success():
    """A successful function returns its own value untouched (no envelope wrapping)."""

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def my_tool(x):
        return x + 1

    assert my_tool(5) == 6


def test_api_tool_timeout_returns_error_envelope():
    """A call exceeding the timeout returns a JSON error envelope, fast."""

    @api_tool(provider="TestProvider", endpoint="TestEndpoint", timeout=0.1)
    def slow_tool():
        time.sleep(1.0)
        return "slow_success"

    start = time.time()
    result = slow_tool()
    duration = time.time() - start

    payload = _envelope(result)
    assert payload["success"] is False
    assert "timed out" in payload["error"]
    assert duration < 0.4


def test_api_tool_http_429_retry_success(mocker):
    """A 429 triggers a retry; success on the retry is returned verbatim.

    The first pause is the SHORTEST of the escalating ladder: a throttle that clears
    quickly must not cost the caller the long waits meant for one that does not.
    """
    from crewai_custom_tools.core.decorators import _PAUSES_429

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
    mock_sleep.assert_called_once_with(_PAUSES_429[0])


def test_api_tool_http_429_retry_timeout(mocker):
    """If the retry itself times out, an error envelope is returned."""
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
        time.sleep(0.5)
        return "slow_success"

    payload = _envelope(rate_limited_slow_tool())
    assert payload["success"] is False
    assert call_count == 2


def test_api_tool_other_http_error_no_retry():
    """Non-429 HTTP errors are not retried and surface as an error envelope."""
    call_count = 0

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def http_error_tool():
        nonlocal call_count
        call_count += 1
        response = requests.Response()
        response.status_code = 500
        raise requests.exceptions.HTTPError("Internal Server Error", response=response)

    payload = _envelope(http_error_tool())
    assert payload["success"] is False
    assert "TestProvider" in payload["error"]
    assert call_count == 1


def test_api_tool_unexpected_exception_returns_error_envelope():
    """Any unexpected exception is caught and returned as an error envelope."""

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def broken_tool():
        raise ValueError("Generic DB error")

    payload = _envelope(broken_tool())
    assert payload["success"] is False
    assert "Generic DB error" in payload["error"]


def test_api_tool_acquires_rate_limit_token(mocker):
    """The api_tool decorator acquires a rate-limit token from the registry."""
    from crewai_custom_tools.core import decorators

    registry = mocker.Mock()
    mocker.patch.object(decorators, "get_rate_limiter", return_value=registry)

    @decorators.api_tool(provider="DemoProvider", endpoint="DemoEndpoint")
    def sample() -> str:
        return "done"

    assert sample() == "done"
    registry.acquire.assert_called_once_with("DemoProvider")


def test_api_tool_converts_rate_limit_exceeded_to_err(mocker):
    import json

    from crewai_custom_tools.core import decorators
    from crewai_custom_tools.core.rate_limiter import RateLimitExceeded

    registry = mocker.Mock()
    registry.acquire.side_effect = RateLimitExceeded("DemoProvider: rate-limit wait exceeded 0.0s")
    mocker.patch.object(decorators, "get_rate_limiter", return_value=registry)

    @decorators.api_tool(provider="DemoProvider", endpoint="DemoEndpoint")
    def sample() -> str:
        return "never reached"

    payload = json.loads(sample())
    assert payload["success"] is False
    assert "rate-limit" in payload["error"]


# --- reprise sur 429 : durée et Retry-After ---


def _reponse_429(retry_after=None):
    reponse = requests.Response()
    reponse.status_code = 429
    if retry_after is not None:
        reponse.headers["Retry-After"] = str(retry_after)
    return requests.exceptions.HTTPError(response=reponse)


def test_backoff_429_reprend_plusieurs_fois(mocker):
    """Une reprise unique à 2 s ne survit à aucun étranglement réel.

    Mesuré en production sur upload.wikimedia.org : avertissement à 18:26:14, échec à
    18:26:16 — la reprise repartait pendant que le quota était encore épuisé, donc
    toutes les images d'un run échouaient.
    """
    pauses = []
    mocker.patch("crewai_custom_tools.core.decorators.sleep", side_effect=pauses.append)
    appels = {"n": 0}

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def toujours_429():
        appels["n"] += 1
        raise _reponse_429()

    payload = _envelope(toujours_429())
    assert payload["success"] is False
    assert appels["n"] > 2, "une seule reprise ne suffit pas"
    assert pauses == sorted(pauses), f"les pauses doivent croître : {pauses}"
    assert max(pauses) >= 20, f"la plus longue pause reste trop courte : {pauses}"


def test_backoff_429_honore_retry_after(mocker):
    """Quand le serveur dit combien attendre, on l'écoute au lieu de deviner."""
    pauses = []
    mocker.patch("crewai_custom_tools.core.decorators.sleep", side_effect=pauses.append)

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def _429_avec_consigne():
        raise _reponse_429(retry_after=7)

    _envelope(_429_avec_consigne())
    assert pauses and all(p == 7 for p in pauses), pauses


def test_backoff_429_borne_un_retry_after_delirant(mocker):
    """Un `Retry-After` d'une journée ne doit pas figer l'outil pour une journée."""
    pauses = []
    mocker.patch("crewai_custom_tools.core.decorators.sleep", side_effect=pauses.append)

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def _429_absurde():
        raise _reponse_429(retry_after=86400)

    _envelope(_429_absurde())
    assert pauses and max(pauses) <= 120, pauses


def test_backoff_429_ignore_un_retry_after_illisible(mocker):
    """`Retry-After` peut porter une date HTTP : illisible en entier, on retombe sur la pause prévue."""
    pauses = []
    mocker.patch("crewai_custom_tools.core.decorators.sleep", side_effect=pauses.append)

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def _429_date():
        raise _reponse_429(retry_after="Wed, 21 Oct 2026 07:28:00 GMT")

    _envelope(_429_date())
    assert pauses and all(isinstance(p, int | float) and p > 0 for p in pauses), pauses


def test_backoff_429_rend_la_main_des_que_la_reprise_passe(mocker):
    """Le premier succès arrête les reprises : pas de pause inutile après."""
    pauses = []
    mocker.patch("crewai_custom_tools.core.decorators.sleep", side_effect=pauses.append)
    appels = {"n": 0}

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def _429_puis_ok():
        appels["n"] += 1
        if appels["n"] == 1:
            raise _reponse_429()
        return "ok"

    assert _429_puis_ok() == "ok"
    assert len(pauses) == 1, pauses


def test_une_erreur_http_qui_n_est_pas_429_ne_dort_pas(mocker):
    """404 n'est pas un étranglement : aucune pause, aucune reprise."""
    pauses = []
    mocker.patch("crewai_custom_tools.core.decorators.sleep", side_effect=pauses.append)
    appels = {"n": 0}

    @api_tool(provider="TestProvider", endpoint="TestEndpoint")
    def _404():
        appels["n"] += 1
        reponse = requests.Response()
        reponse.status_code = 404
        raise requests.exceptions.HTTPError(response=reponse)

    _envelope(_404())
    assert appels["n"] == 1 and pauses == []
