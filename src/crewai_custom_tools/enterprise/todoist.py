"""Todoist API integrations for task and project synchronization."""

import logging
import os
from typing import Any, Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models.todoist_models import TodoistToolInput

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.todoist.com/rest/v2"


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

    @api_tool(provider="Todoist", endpoint="TaskSync")
    def _run(
        self,
        action: str,
        project_id: str | None = None,
        task_id: str | None = None,
        task_content: str | None = None,
        due_string: str | None = None,
        priority: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Run the Todoist tool with the specified action."""
        action = action.lower()

        if action == "get_tasks":
            params = {"project_id": project_id} if project_id else {}
            response = requests.get(
                f"{_BASE_URL}/tasks", headers=self._get_headers(), params=params, timeout=10
            )
            response.raise_for_status()
            tasks = response.json()
            return ok({"count": len(tasks), "tasks": tasks})

        if action == "create_task":
            if not task_content:
                return err("task_content is required for create_task")
            payload: dict[str, Any] = {"content": task_content}
            if project_id:
                payload["project_id"] = project_id
            if due_string:
                payload["due_string"] = due_string
            if priority:
                payload["priority"] = priority
            response = requests.post(
                f"{_BASE_URL}/tasks", headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            return ok({"created": response.json()})

        if action == "complete_task":
            if not task_id:
                return err("task_id is required for complete_task")
            response = requests.post(
                f"{_BASE_URL}/tasks/{task_id}/close", headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()
            return ok({"completed": task_id})

        if action == "get_projects":
            response = requests.get(
                f"{_BASE_URL}/projects", headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()
            projects = response.json()
            return ok({"count": len(projects), "projects": projects})

        return err(
            f"Unknown action '{action}'. Valid actions: get_tasks, create_task, "
            "complete_task, get_projects."
        )
