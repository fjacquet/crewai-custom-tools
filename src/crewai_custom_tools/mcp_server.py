"""Model Context Protocol (MCP) server for crewai-custom-tools.

Every tool exported from ``crewai_custom_tools.__all__`` is registered with the FastMCP
server automatically, so the MCP surface stays in parity with the library: export a new
tool once and it shows up here too — no hand-written wrapper per tool.

Each MCP tool takes the same parameters as the underlying tool's ``args_schema`` and
returns the tool's JSON ``{"success", "data", "error"}`` envelope. Launch via the
``crewai-custom-tools-mcp`` console entrypoint (stdio JSON-RPC).
"""

import inspect
import logging
import re
from typing import Any

from crewai.tools import BaseTool
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

import crewai_custom_tools as _pkg

logger = logging.getLogger("crewai_custom_tools.mcp_server")

mcp = FastMCP("crewai-custom-tools")


def _mcp_name(name: str) -> str:
    """Slugify a tool's display name into an MCP-spec name (a-z 0-9 _ - . only).

    Legacy tools use human-readable names with spaces ("FRED Macro Indicators Tool");
    the MCP spec allows only ``[A-Za-z0-9_.-]``, so normalise for the MCP surface while
    the library keeps the original ``tool.name``.
    """
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip().lower()).strip("_")
    return slug or "tool"


def _iter_tool_classes():
    """Yield every exported BaseTool subclass (skips helpers like validate_html)."""
    for name in _pkg.__all__:
        obj = getattr(_pkg, name, None)
        if isinstance(obj, type) and issubclass(obj, BaseTool):
            yield obj


def _schema_params(instance: BaseTool) -> list[inspect.Parameter]:
    """Derive keyword-only parameters from a tool's args_schema (empty if none)."""
    schema = getattr(instance, "args_schema", None)
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        return []
    params = []
    for fname, field in schema.model_fields.items():
        annotation = field.annotation if field.annotation is not None else str
        default = inspect.Parameter.empty if field.is_required() else field.default
        params.append(
            inspect.Parameter(
                fname,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )
    return params


def _make_handler(instance: BaseTool, params: list[inspect.Parameter]):
    """Build a handler with an explicit signature so FastMCP infers the input schema."""

    def handler(**kwargs: Any) -> str:
        return instance._run(**kwargs)

    handler.__signature__ = inspect.Signature(params)
    handler.__annotations__ = {p.name: p.annotation for p in params}
    handler.__annotations__["return"] = str
    return handler


def register_all() -> tuple[int, list[tuple[str, str]]]:
    """Register every exported tool with the FastMCP server.

    Returns ``(registered_count, skipped)`` where ``skipped`` is a list of
    ``(class_name, reason)``. A tool that fails to construct or has a duplicate name is
    logged and skipped rather than breaking the whole server.
    """
    registered = 0
    skipped: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for cls in _iter_tool_classes():
        try:
            instance = cls()
            name = _mcp_name(instance.name)
            if name in seen_names:
                skipped.append((cls.__name__, f"duplicate MCP name {name!r}"))
                continue
            handler = _make_handler(instance, _schema_params(instance))
            mcp.add_tool(handler, name=name, description=instance.description)
            seen_names.add(name)
            registered += 1
        except Exception as e:
            logger.warning("Skipping MCP registration for %s: %s", cls.__name__, e)
            skipped.append((cls.__name__, str(e)))
    return registered, skipped


REGISTERED, SKIPPED = register_all()


def run() -> None:
    """Launch the FastMCP stdio server (configured as a console entrypoint)."""
    mcp.run()
