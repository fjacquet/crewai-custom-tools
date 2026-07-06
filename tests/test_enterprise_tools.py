"""Mock-based unit tests for unified enterprise integration tools."""

import json
import os
import pytest
import requests
from unittest.mock import MagicMock
from crewai_custom_tools.enterprise.todoist import TodoistTool
from crewai_custom_tools.enterprise.airtable import AirtableReaderTool, AirtableTool
from crewai_custom_tools.enterprise.accuweather import AccuWeatherTool
from crewai_custom_tools.enterprise.rag_tools import SaveToRagTool


# ==============================================================================
# 1. Todoist Tool Tests
# ==============================================================================


def test_todoist_get_tasks_success(mocker):
    """Test retrieving tasks from Todoist REST API."""
    mocker.patch.dict(os.environ, {"TODOIST_API_KEY": "test_todoist_token"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "111", "content": "Review Q2 Financials"},
        {"id": "222", "content": "Build Multi-agent Suite"},
    ]
    mocker.patch("requests.get", return_value=mock_response)

    tool = TodoistTool()
    result = tool._run(action="get_tasks")

    assert "Found 2 tasks" in result
    assert "Review Q2 Financials" in result


def test_todoist_create_task_success(mocker):
    """Test creating a task in Todoist REST API."""
    mocker.patch.dict(os.environ, {"TODOIST_API_KEY": "test_todoist_token"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "123", "content": "Verify lockfiles"}
    mocker.patch("requests.post", return_value=mock_response)

    tool = TodoistTool()
    result = tool._run(
        action="create_task", task_content="Verify lockfiles", priority=4
    )

    assert "Task created successfully" in result
    assert "Verify lockfiles" in result


# ==============================================================================
# 2. Airtable and AccuWeather Tests
# ==============================================================================


def test_airtable_read_records_success(mocker):
    """Test reading records from Airtable REST API."""
    mocker.patch.dict(os.environ, {"AIRTABLE_API_KEY": "test_airtable_key"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "records": [
            {"id": "rec123", "fields": {"Name": "John Dupont", "Role": "Director"}}
        ]
    }
    mocker.patch("requests.get", return_value=mock_response)

    tool = AirtableReaderTool()
    result_str = tool._run(base_id="app123", table_name="Personnel")
    result = json.loads(result_str)

    assert len(result) == 1
    assert result[0]["id"] == "rec123"
    assert result[0]["fields"]["Name"] == "John Dupont"


def test_airtable_create_record_success(mocker):
    """Test creating a record in Airtable REST API."""
    mocker.patch.dict(os.environ, {"AIRTABLE_API_KEY": "test_airtable_key"})

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "rec456"}
    mocker.patch("requests.post", return_value=mock_response)

    tool = AirtableTool()
    result = tool._run(
        base_id="app123",
        table_name="Personnel",
        data={"Name": "Alice Smith", "Role": "Engineer"},
    )

    assert "Successfully created record in Airtable: rec456" in result


def test_accuweather_weather_conditions_success(mocker):
    """Test fetching weather key and conditions from AccuWeather REST API."""
    mocker.patch.dict(os.environ, {"ACCUWEATHER_API_KEY": "test_accuweather_key"})

    # Mocking first GET to autocomplete search
    mock_loc_response = mocker.MagicMock()
    mock_loc_response.status_code = 200
    mock_loc_response.json.return_value = [{"Key": "328328", "LocalizedName": "London"}]

    # Mocking second GET to current conditions
    mock_weather_response = mocker.MagicMock()
    mock_weather_response.status_code = 200
    mock_weather_response.json.return_value = [
        {
            "Temperature": {"Metric": {"Value": 18.5, "Unit": "C"}},
            "WeatherText": "Partly sunny",
        }
    ]

    def side_effect(url, *args, **kwargs):
        if "autocomplete" in url:
            return mock_loc_response
        return mock_weather_response

    mocker.patch("requests.get", side_effect=side_effect)

    tool = AccuWeatherTool()
    result = tool._run(location="London")

    assert "Current weather in your location" in result
    assert "18.5" in result
    assert "Partly sunny" in result


# ==============================================================================
# 3. RAG Tools Tests
# ==============================================================================


def test_save_to_rag_tool_success(mocker):
    """Test saving content to RAG vectors store fallback."""
    tool = SaveToRagTool()
    result_str = tool._run(text="Acme PESTEL Analysis results")
    result = json.loads(result_str)

    assert result["status"] == "success"
    assert "Mock-stored" in result["message"]
