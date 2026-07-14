import pytest

from crewai_custom_tools.core.keys import require_api_key


def test_returns_first_set_variable(monkeypatch):
    monkeypatch.delenv("PRIMARY_KEY", raising=False)
    monkeypatch.setenv("FALLBACK_KEY", "sk-fallback")
    assert require_api_key("PRIMARY_KEY", "FALLBACK_KEY", tool_name="DemoTool") == "sk-fallback"


def test_primary_wins_when_both_set(monkeypatch):
    monkeypatch.setenv("PRIMARY_KEY", "sk-primary")
    monkeypatch.setenv("FALLBACK_KEY", "sk-fallback")
    assert require_api_key("PRIMARY_KEY", "FALLBACK_KEY", tool_name="DemoTool") == "sk-primary"


def test_raises_value_error_when_all_missing(monkeypatch):
    monkeypatch.delenv("PRIMARY_KEY", raising=False)
    monkeypatch.delenv("FALLBACK_KEY", raising=False)
    with pytest.raises(ValueError, match="DemoTool requires PRIMARY_KEY or FALLBACK_KEY"):
        require_api_key("PRIMARY_KEY", "FALLBACK_KEY", tool_name="DemoTool")


def test_empty_string_counts_as_missing(monkeypatch):
    monkeypatch.setenv("PRIMARY_KEY", "")
    with pytest.raises(ValueError):
        require_api_key("PRIMARY_KEY", tool_name="DemoTool")
