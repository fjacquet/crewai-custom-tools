"""Airtable table operations and databases tools."""

import json
import logging
import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel
from typing import Any
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.models.airtable_models import (
    AirtableReaderToolInput,
    AirtableToolInput,
)

logger = logging.getLogger(__name__)


class AirtableReaderTool(BaseTool):
    """A tool to read records from an Airtable table."""

    name: str = "airtable_read_records"
    description: str = (
        "A tool for reading all records from a specified Airtable table. "
        "It requires the base ID and table name."
    )
    args_schema: type[BaseModel] = AirtableReaderToolInput

    @api_tool(provider="Airtable", endpoint="ReadRecords", default_return="[]")
    def _run(self, base_id: str, table_name: str) -> str:
        """Run the Airtable tool to read records."""
        api_key = os.getenv("AIRTABLE_API_KEY")
        if not api_key:
            return "Error: AIRTABLE_API_KEY environment variable not set."

        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {"Authorization": f"Bearer {api_key}"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        records = response.json().get("records", [])
        return json.dumps(records)


class AirtableTool(BaseTool):
    """A tool to create a record in an Airtable table."""

    name: str = "airtable_create_record"
    description: str = (
        "A tool for creating a new record in a specified Airtable table. "
        "It requires the base ID, table name, and the data for the new record."
    )
    args_schema: type[BaseModel] = AirtableToolInput

    @api_tool(
        provider="Airtable",
        endpoint="CreateRecord",
        default_return="Error: Failed to create record.",
    )
    def _run(self, base_id: str, table_name: str, data: dict[str, Any]) -> str:
        """Run the Airtable tool to create a record."""
        api_key = os.getenv("AIRTABLE_API_KEY")
        if not api_key:
            return "Error: AIRTABLE_API_KEY environment variable not set."

        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"fields": data}

        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        record_id = response.json().get("id")
        return f"Successfully created record in Airtable: {record_id}"
