"""Mock-based unit tests for unified enterprise integration tools (envelope contract)."""

import json
import os
import types

from crewai_custom_tools.enterprise.todoist import TodoistTool
from crewai_custom_tools.enterprise.airtable import AirtableReaderTool, AirtableTool
from crewai_custom_tools.enterprise.accuweather import AccuWeatherTool
from crewai_custom_tools.enterprise.rag_tools import SaveToRagTool


def _envelope(result: str) -> dict:
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# ==============================================================================
# 1. Todoist
# ==============================================================================


def test_todoist_get_tasks_success(mocker):
    """get_tasks returns a structured envelope and parses the body only once."""
    mocker.patch.dict(os.environ, {"TODOIST_API_KEY": "test_todoist_token"})

    mock_response = mocker.MagicMock()
    mock_response.json.return_value = [
        {"id": "111", "content": "Review Q2 Financials"},
        {"id": "222", "content": "Build Multi-agent Suite"},
    ]
    mocker.patch("requests.get", return_value=mock_response)

    payload = _envelope(TodoistTool()._run(action="get_tasks"))

    assert payload["success"] is True
    assert payload["data"]["count"] == 2
    assert payload["data"]["tasks"][0]["content"] == "Review Q2 Financials"
    # L13: the body must be deserialized exactly once, not twice.
    assert mock_response.json.call_count == 1


def test_todoist_create_task_success(mocker):
    mocker.patch.dict(os.environ, {"TODOIST_API_KEY": "test_todoist_token"})
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"id": "123", "content": "Verify lockfiles"}
    mocker.patch("requests.post", return_value=mock_response)

    payload = _envelope(
        TodoistTool()._run(action="create_task", task_content="Verify lockfiles", priority=4)
    )
    assert payload["success"] is True
    assert payload["data"]["created"]["content"] == "Verify lockfiles"


def test_todoist_create_task_requires_content(mocker):
    mocker.patch.dict(os.environ, {"TODOIST_API_KEY": "test_todoist_token"})
    payload = _envelope(TodoistTool()._run(action="create_task"))
    assert payload["success"] is False
    assert "task_content" in payload["error"]


# ==============================================================================
# 2. Airtable
# ==============================================================================


def test_airtable_read_records_success(mocker):
    mocker.patch.dict(os.environ, {"AIRTABLE_API_KEY": "test_airtable_key"})
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "records": [{"id": "rec123", "fields": {"Name": "John Dupont"}}]
    }
    mocker.patch("requests.get", return_value=mock_response)

    payload = _envelope(AirtableReaderTool()._run(base_id="app123", table_name="Personnel"))
    assert payload["success"] is True
    assert payload["data"][0]["id"] == "rec123"


def test_airtable_table_name_is_url_encoded(mocker):
    """M9: a table name with a space must be percent-encoded in the request URL."""
    mocker.patch.dict(os.environ, {"AIRTABLE_API_KEY": "test_airtable_key"})
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {"records": []}

    AirtableReaderTool()._run(base_id="app123", table_name="Project Tasks")

    called_url = mock_get.call_args[0][0]
    assert "Project%20Tasks" in called_url
    assert " " not in called_url


def test_airtable_create_record_success(mocker):
    mocker.patch.dict(os.environ, {"AIRTABLE_API_KEY": "test_airtable_key"})
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"id": "rec456"}
    mocker.patch("requests.post", return_value=mock_response)

    payload = _envelope(
        AirtableTool()._run(base_id="app123", table_name="Personnel", data={"Name": "Alice"})
    )
    assert payload["success"] is True
    assert payload["data"]["record_id"] == "rec456"


def test_airtable_create_rejects_empty_data(mocker):
    """L14: creating with an empty fields dict returns an error, not an empty record."""
    mocker.patch.dict(os.environ, {"AIRTABLE_API_KEY": "test_airtable_key"})
    post = mocker.patch("requests.post")

    payload = _envelope(AirtableTool()._run(base_id="app123", table_name="T", data={}))
    assert payload["success"] is False
    assert "non-empty" in payload["error"]
    post.assert_not_called()


# ==============================================================================
# 3. AccuWeather
# ==============================================================================


def test_accuweather_conditions_success_over_https(mocker):
    """M7: conditions returned in the envelope and every request uses https."""
    mocker.patch.dict(os.environ, {"ACCUWEATHER_API_KEY": "test_accuweather_key"})

    loc = mocker.MagicMock()
    loc.json.return_value = [{"Key": "328328", "LocalizedName": "London"}]
    weather = mocker.MagicMock()
    weather.json.return_value = [
        {"Temperature": {"Metric": {"Value": 18.5, "Unit": "C"}}, "WeatherText": "Partly sunny"}
    ]

    called_urls = []

    def side_effect(url, *args, **kwargs):
        called_urls.append(url)
        return loc if "autocomplete" in url else weather

    mocker.patch("requests.get", side_effect=side_effect)

    payload = _envelope(AccuWeatherTool()._run(location="London"))
    assert payload["success"] is True
    assert payload["data"]["temperature"] == 18.5
    assert payload["data"]["conditions"] == "Partly sunny"
    assert called_urls and all(u.startswith("https://") for u in called_urls)


# ==============================================================================
# 4. SaveToRag (H8 — never a fake success)
# ==============================================================================


def test_save_to_rag_success(mocker):
    """A working RagTool.add yields a success envelope."""
    fake = types.ModuleType("crewai_tools")
    rag_instance = mocker.MagicMock()
    fake.RagTool = mocker.MagicMock(return_value=rag_instance)
    mocker.patch.dict("sys.modules", {"crewai_tools": fake})

    payload = _envelope(SaveToRagTool()._run(text="Acme PESTEL results"))
    assert payload["success"] is True
    assert payload["data"]["stored"] is True
    rag_instance.add.assert_called_once()


def test_save_to_rag_failure_returns_error(mocker):
    """H8: when storage fails, the tool must report failure — never a fake success."""
    # Force the `from crewai_tools import RagTool` to raise ImportError.
    mocker.patch.dict("sys.modules", {"crewai_tools": None})

    payload = _envelope(SaveToRagTool()._run(text="data that will not persist"))
    assert payload["success"] is False
    assert payload["error"] is not None
