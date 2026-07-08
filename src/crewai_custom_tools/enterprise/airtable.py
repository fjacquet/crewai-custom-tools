"""Airtable table operations and databases tools."""

import logging
import os
import urllib.parse
from typing import Any

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models.airtable_models import (
    AirtableReaderToolInput,
    AirtableToolInput,
)

logger = logging.getLogger(__name__)


def _table_url(base_id: str, table_name: str) -> str:
    """Build the Airtable REST URL, percent-encoding both path segments.

    Table names commonly contain spaces/special chars (e.g. 'Project Tasks'), which
    would otherwise produce a malformed request path.
    """
    return (
        "https://api.airtable.com/v0/"
        f"{urllib.parse.quote(base_id, safe='')}/"
        f"{urllib.parse.quote(table_name, safe='')}"
    )


class AirtableReaderTool(BaseTool):
    """A tool to read records from an Airtable table."""

    name: str = "airtable_read_records"
    description: str = (
        "A tool for reading all records from a specified Airtable table. "
        "It requires the base ID and table name."
    )
    args_schema: type[BaseModel] = AirtableReaderToolInput

    @api_tool(provider="Airtable", endpoint="ReadRecords")
    def _run(self, base_id: str, table_name: str) -> str:
        """Run the Airtable tool to read records."""
        api_key = os.getenv("AIRTABLE_API_KEY")
        if not api_key:
            return err("AIRTABLE_API_KEY environment variable not set")

        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(
            _table_url(base_id, table_name), headers=headers, timeout=10
        )
        response.raise_for_status()
        return ok(response.json().get("records", []))


class AirtableTool(BaseTool):
    """A tool to create a record in an Airtable table."""

    name: str = "airtable_create_record"
    description: str = (
        "A tool for creating a new record in a specified Airtable table. "
        "It requires the base ID, table name, and the data for the new record."
    )
    args_schema: type[BaseModel] = AirtableToolInput

    @api_tool(provider="Airtable", endpoint="CreateRecord")
    def _run(self, base_id: str, table_name: str, data: dict[str, Any]) -> str:
        """Run the Airtable tool to create a record."""
        api_key = os.getenv("AIRTABLE_API_KEY")
        if not api_key:
            return err("AIRTABLE_API_KEY environment variable not set")
        if not data:
            return err("data must be a non-empty dict of fields")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            _table_url(base_id, table_name),
            headers=headers,
            json={"fields": data},
            timeout=10,
        )
        response.raise_for_status()
        return ok({"record_id": response.json().get("id")})
