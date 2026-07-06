"""Todoist API integrations for task and project synchronization."""

import logging
import os
import requests
from typing import Any, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.models.todoist_models import TodoistToolInput

logger = logging.getLogger(__name__)


class TodoistTool(BaseTool):
    """A tool to manage projects and task synchronization in Todoist."""

    name: str = "todoist_manager"
    description: str = (
        "A tool for interacting with the Todoist API. "
        "Supports getting tasks, creating tasks, completing tasks, and listing projects. "
        "Requires TODOIST_API_KEY environment variable."
    )
    args_schema: type[BaseModel] = TodoistToolInput

    def _get_headers(self) -> dict[str, str]:
        api_token = os.getenv("TODOIST_API_KEY")
        if not api_token:
            raise ValueError("TODOIST_API_KEY environment variable not set.")
        return {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    @api_tool(
        provider="Todoist",
        endpoint="TaskSync",
        default_return="Error: Todoist request failed.",
    )
    def _run(
        self,
        action: str,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        task_content: Optional[str] = None,
        due_string: Optional[str] = None,
        priority: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Run the Todoist tool with specified actions."""
        base_url = "https://api.todoist.com/rest/v2"
        action = action.lower()

        # 1. Action: Get Tasks
        if action == "get_tasks":
            url = f"{base_url}/tasks"
            params = {}
            if project_id:
                params["project_id"] = project_id
            response = requests.get(
                url, headers=self._get_headers(), params=params, timeout=10
            )
            response.raise_for_status()
            return f"Found {len(response.json())} tasks: {response.json()}"

        # 2. Action: Create Task
        if action == "create_task":
            if not task_content:
                return "Error: task_content is required for create_task action"
            url = f"{base_url}/tasks"
            payload = {"content": task_content}
            if project_id:
                payload["project_id"] = project_id
            if due_string:
                payload["due_string"] = due_string
            if priority:
                payload["priority"] = priority
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            return f"Task created successfully: {response.json()}"

        # 3. Action: Complete Task
        if action == "complete_task":
            if not task_id:
                return "Error: task_id is required for complete_task action"
            url = f"{base_url}/tasks/{task_id}/close"
            response = requests.post(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            return f"Task {task_id} completed successfully"

        # 4. Action: Get Projects
        if action == "get_projects":
            url = f"{base_url}/projects"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            return f"Found {len(response.json())} projects: {response.json()}"

        return f"Error: Unknown action '{action}'. Valid actions: get_tasks, create_task, complete_task, get_projects."
