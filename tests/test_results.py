"""Tests for the ToolResult envelope in crewai_custom_tools/core/results.py."""

import json

from crewai_custom_tools.core.results import ToolResult, err, ok


def test_ok_wraps_data():
    payload = json.loads(ok({"answer": 42}))
    assert payload == {"success": True, "data": {"answer": 42}, "error": None}


def test_ok_defaults_to_null_data():
    payload = json.loads(ok())
    assert payload == {"success": True, "data": None, "error": None}


def test_err_carries_message():
    payload = json.loads(err("boom"))
    assert payload == {"success": False, "data": None, "error": "boom"}


def test_err_can_attach_partial_data():
    payload = json.loads(err("partial failure", data={"got": 1}))
    assert payload["success"] is False
    assert payload["data"] == {"got": 1}
    assert payload["error"] == "partial failure"


def test_tool_result_serializes_non_json_types():
    """Non-JSON-native values (e.g. sets) fall back to str() rather than raising."""
    result = ToolResult(success=True, data={"tags": {"a", "b"}}).to_json()
    # Must be valid JSON and round-trippable.
    assert json.loads(result)["success"] is True
