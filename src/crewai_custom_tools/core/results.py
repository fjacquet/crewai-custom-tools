"""Standard result envelope shared by every tool.

Every tool's ``_run`` returns a JSON string in the canonical shape::

    {"success": bool, "data": <any> | null, "error": <str> | null}

Use the :func:`ok` / :func:`err` helpers rather than hand-building the dict, so
the contract stays consistent across the whole library. ``success`` lets a
caller distinguish a genuine failure from an empty-but-successful result — the
ambiguity that caused most of the silent-failure bugs in the first ports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Immutable envelope describing a tool outcome."""

    success: bool
    data: Any = None
    error: str | None = None

    def to_json(self) -> str:
        """Serialize to the canonical JSON string."""
        return json.dumps(
            {"success": self.success, "data": self.data, "error": self.error},
            default=str,
        )


def ok(data: Any = None) -> str:
    """Return a JSON success envelope wrapping ``data``."""
    return ToolResult(success=True, data=data).to_json()


def err(message: str, data: Any = None) -> str:
    """Return a JSON error envelope carrying ``message``."""
    return ToolResult(success=False, data=data, error=message).to_json()


class ToolResultError(RuntimeError):
    """Raised by :func:`parse_tool_result` when an envelope reports failure."""

    def __init__(self, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.data = data


def parse_tool_result(raw: str) -> Any:
    """Parse a canonical envelope string and return its ``data`` payload.

    Raises:
        ToolResultError: if ``raw`` is not a valid envelope, or the envelope
            has ``success=False`` (the error message and any partial ``data``
            are carried on the exception).
    """
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ToolResultError(f"Not a valid tool envelope: {exc}") from exc
    if not isinstance(payload, dict) or "success" not in payload:
        raise ToolResultError("Not a valid tool envelope: missing 'success' key")
    if not payload["success"]:
        raise ToolResultError(payload.get("error") or "Tool reported failure", data=payload.get("data"))
    return payload.get("data")
