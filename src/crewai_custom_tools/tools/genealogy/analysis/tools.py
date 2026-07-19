"""On-demand analysis tools for agents over the pure rules engine.

Thin BaseTool wrappers: fetch facts via FactsFetcher, run the pure R1-R10 rules,
return structured anomalies. Read-only by design — no write tool may exist here.
"""

import logging

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.genealogy.analysis.duplicates import find_duplicates
from crewai_custom_tools.tools.genealogy.analysis.rules import check_family, check_person
from crewai_custom_tools.tools.genealogy.gramps.client import get_client
from crewai_custom_tools.tools.genealogy.gramps.facts import FactsFetcher

logger = logging.getLogger(__name__)

MAX_DUPLICATE_SCOPE = 500  # hard bound: never the full-tree O(n²) from an agent


class GenealogyCheckPersonInput(BaseModel):
    """Input schema for GenealogyCheckPersonTool."""

    handle: str | None = Field(None, description="Internal Gramps handle of the person.")
    gramps_id: str | None = Field(None, description="Human-readable ID (I0042...).")


class GenealogyCheckPersonTool(BaseTool):
    """Re-run the deterministic consistency rules (R1-R10) on one person, on demand."""

    name: str = "genealogy_check_person"
    description: str = (
        "Runs the deterministic genealogy consistency rules on one person (impossible "
        "ages, incoherent dates, missing sources...) including their families, and "
        "returns the structured anomalies. Read-only."
    )
    args_schema: type[BaseModel] = GenealogyCheckPersonInput

    @api_tool(provider="GrampsWeb", endpoint="CheckPerson")
    def _run(self, handle: str | None = None, gramps_id: str | None = None) -> str:
        client = get_client()
        if not handle:
            if not gramps_id:
                return err("genealogy_check_person: provide either handle or gramps_id")
            handle = (client.find_by_gramps_id("people", gramps_id) or {}).get("handle")
            if not handle:
                return err(f"genealogy_check_person: no person with gramps_id {gramps_id}")

        fetcher = FactsFetcher(client)
        person = fetcher.get_person_facts(handle)
        if person is None:
            return err(f"genealogy_check_person: person not found: {handle}")

        anomalies = list(check_person(person))
        for fam_handle in [*person.parent_family_handles, *person.family_handles]:
            family = fetcher.get_family_facts(fam_handle)
            if family is None:
                continue
            related = {}
            for h in filter(None, [family.father_handle, family.mother_handle,
                                   *family.child_handles]):
                pf = fetcher.get_person_facts(h)
                if pf is not None:
                    related[h] = pf
            anomalies.extend(check_family(family, related))

        return ok({
            "gramps_id": person.gramps_id, "handle": person.handle, "name": person.name,
            "anomalies": [a.model_dump() for a in anomalies],
        })


class GenealogyFindDuplicatesInput(BaseModel):
    """Input schema for GenealogyFindDuplicatesTool."""

    surname: str | None = Field(
        None, description="Restrict the search to people matching this surname."
    )
    limit: int = Field(
        200, description=f"Max people compared (bounded at {MAX_DUPLICATE_SCOPE})."
    )
    threshold: float = Field(0.85, description="Name-similarity threshold (0..1).")


class GenealogyFindDuplicatesTool(BaseTool):
    """Find candidate duplicate persons (R10) within a bounded scope."""

    name: str = "genealogy_find_duplicates"
    description: str = (
        "Finds candidate duplicate persons (normalized name + birth-year window) within "
        "a bounded scope — optionally restricted to one surname. Read-only."
    )
    args_schema: type[BaseModel] = GenealogyFindDuplicatesInput

    @api_tool(provider="GrampsWeb", endpoint="FindDuplicates", timeout=60.0)
    def _run(self, surname: str | None = None, limit: int = 200,
             threshold: float = 0.85) -> str:
        limit = min(limit, MAX_DUPLICATE_SCOPE)
        client = get_client()
        fetcher = FactsFetcher(client)

        if surname:
            hits = client.search(surname, pagesize=limit)
            handles = [
                h.get("handle") or (h.get("object") or {}).get("handle")
                for h in hits
                if h.get("object_type") == "person"
            ]
            people = [p for h in handles[:limit]
                      if h and (p := fetcher.get_person_facts(h)) is not None]
        else:
            people, page = [], 1
            while len(people) < limit:
                batch = fetcher.list_people_facts(page=page, pagesize=min(100, limit))
                if not batch:
                    break
                people.extend(batch)
                page += 1
            people = people[:limit]

        pairs = find_duplicates(people, threshold=threshold)
        return ok({
            "people_compared": len(people),
            "pairs": [p.model_dump() for p in pairs],
        })
