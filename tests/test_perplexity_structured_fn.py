import httpx
import pytest
from pydantic import BaseModel

from crewai_custom_tools.tools.web.perplexity_structured import perplexity_structured


class FactPack(BaseModel):
    headline: str
    confidence: float


@pytest.fixture()
def pplx_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")


def _client_returning(mocker, payload=None, exc=None):
    """Patch httpx.AsyncClient so post() returns payload or raises exc."""
    response = mocker.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client = mocker.AsyncMock()
    client.__aenter__.return_value = client
    if exc is not None:
        client.post.side_effect = exc
    else:
        client.post.return_value = response
    return mocker.patch(
        "crewai_custom_tools.tools.web.perplexity_structured.httpx.AsyncClient",
        return_value=client,
    )


async def test_returns_validated_instance(pplx_key, mocker):
    _client_returning(
        mocker,
        payload={"choices": [{"message": {"content": '{"headline": "Up", "confidence": 0.9}'}}]},
    )
    result = await perplexity_structured(prompt="q", schema=FactPack)
    assert result == FactPack(headline="Up", confidence=0.9)


async def test_returns_none_on_transport_error(pplx_key, mocker):
    _client_returning(mocker, exc=httpx.ConnectError("boom"))
    assert await perplexity_structured(prompt="q", schema=FactPack) is None


async def test_returns_none_on_invalid_payload(pplx_key, mocker):
    _client_returning(mocker, payload={"choices": [{"message": {"content": "not json"}}]})
    assert await perplexity_structured(prompt="q", schema=FactPack) is None


async def test_missing_key_raises_value_error(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    with pytest.raises(ValueError):
        await perplexity_structured(prompt="q", schema=FactPack)
