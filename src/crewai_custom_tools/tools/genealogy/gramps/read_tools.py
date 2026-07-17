"""Read-only CrewAI tools over the Gramps Web API.

Thin BaseTool wrappers around client.get_client(). Phase 0 is read-only by
design (spec §2.1): no write tool may exist in this module.
"""

import logging

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.genealogy.gramps.client import get_client

logger = logging.getLogger(__name__)

COUNTED_TYPES = (
    "people", "families", "events", "places", "sources",
    "citations", "repositories", "media", "notes", "tags",
)


class GrampsSearchInput(BaseModel):
    """Input schema for GrampsSearchTool."""

    query: str = Field(..., description="Full-text query across all Gramps record types.")
    page: int = Field(1, description="Result page (1-based).")
    pagesize: int = Field(20, description="Results per page.")


class GrampsSearchTool(BaseTool):
    """Full-text search across the whole Gramps tree."""

    name: str = "gramps_search"
    description: str = (
        "Searches the Gramps genealogy database (people, families, events, places, "
        "sources, notes...) with a full-text query. Read-only."
    )
    args_schema: type[BaseModel] = GrampsSearchInput

    @api_tool(provider="GrampsWeb", endpoint="Search")
    def _run(self, query: str, page: int = 1, pagesize: int = 20) -> str:
        return ok(get_client().search(query, page=page, pagesize=pagesize))


class GrampsGetObjectInput(BaseModel):
    """Input schema for GrampsGetObjectTool."""

    object_type: str = Field(
        ...,
        description="Gramps object type: people, families, events, places, sources, "
        "citations, repositories, media or notes.",
    )
    handle: str | None = Field(None, description="Internal Gramps handle.")
    gramps_id: str | None = Field(None, description="Human-readable ID (I0042, F0007...).")


class GrampsGetObjectTool(BaseTool):
    """Fetch one Gramps object by handle or gramps_id."""

    name: str = "gramps_get_object"
    description: str = (
        "Fetches the full record of one Gramps object (person, family, event...) "
        "by handle or by gramps_id. Read-only."
    )
    args_schema: type[BaseModel] = GrampsGetObjectInput

    @api_tool(provider="GrampsWeb", endpoint="GetObject")
    def _run(
        self,
        object_type: str,
        handle: str | None = None,
        gramps_id: str | None = None,
    ) -> str:
        if handle:
            return ok(get_client().get_object(object_type, handle))
        if gramps_id:
            return ok(get_client().find_by_gramps_id(object_type, gramps_id))
        return err("gramps_get_object: provide either handle or gramps_id")


class GrampsListPeopleInput(BaseModel):
    """Input schema for GrampsListPeopleTool."""

    page: int = Field(1, description="Page number (1-based).")
    pagesize: int = Field(25, description="People per page.")


class GrampsListPeopleTool(BaseTool):
    """Paginated list of people sorted by gramps_id."""

    name: str = "gramps_list_people"
    description: str = "Lists people in the Gramps tree, paginated, sorted by gramps_id. Read-only."
    args_schema: type[BaseModel] = GrampsListPeopleInput

    @api_tool(provider="GrampsWeb", endpoint="ListPeople")
    def _run(self, page: int = 1, pagesize: int = 25) -> str:
        return ok(get_client().list_people(page=page, pagesize=pagesize))


class GrampsTreeStatsInput(BaseModel):
    """Input schema for GrampsTreeStatsTool (no parameters)."""


class GrampsTreeStatsTool(BaseTool):
    """Object counts per type + tree name."""

    name: str = "gramps_tree_stats"
    description: str = (
        "Returns the Gramps tree name and the number of objects of each type "
        "(people, families, events, places, sources, citations...). Read-only."
    )
    args_schema: type[BaseModel] = GrampsTreeStatsInput

    @api_tool(provider="GrampsWeb", endpoint="TreeStats", timeout=60.0)
    def _run(self) -> str:
        client = get_client()
        counts = {t: client.count_objects(t) for t in COUNTED_TYPES}
        info = client.get_tree_info()
        return ok({"tree_name": info.get("name"), "counts": counts})


class GrampsTimelineInput(BaseModel):
    """Input schema for GrampsTimelineTool."""

    handle: str = Field(..., description="Handle of the person.")


class GrampsTimelineTool(BaseTool):
    """Chronological life events of one person."""

    name: str = "gramps_person_timeline"
    description: str = "Returns the chronological timeline of one person's life events. Read-only."
    args_schema: type[BaseModel] = GrampsTimelineInput

    @api_tool(provider="GrampsWeb", endpoint="Timeline")
    def _run(self, handle: str) -> str:
        return ok(get_client().get_timeline(handle))
