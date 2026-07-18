"""Write-side CrewAI tools over the Gramps Web API.

First writer in the genealogy domain. GrampsUpdateNameTool re-capitalizes a
person's primary name in place and refuses any change that is not purely a
casing change (the invariant), so it can never re-spell a name.
"""

import logging
import os

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.genealogy.gramps.client import get_client
from crewai_custom_tools.tools.genealogy.standardize.names import (
    is_case_only_change,
    is_incomplete_name,
    needs_normalization,
    normalize_case,
)

logger = logging.getLogger(__name__)


class GrampsUpdateNameInput(BaseModel):
    """Input schema for GrampsUpdateNameTool."""

    handle: str = Field(..., description="Handle of the person whose primary name to re-case.")
    dry_run: bool = Field(False, description="If true, compute the changes but do not write.")


class GrampsUpdateNameTool(BaseTool):
    """Re-capitalize a person's primary name (casing only; never re-spells)."""

    name: str = "gramps_update_name_case"
    description: str = (
        "Normalizes the capitalization of one person's primary name (first name and "
        "surnames) in Gramps. Only changes casing — refuses any change that alters the "
        "letters, and never touches incomplete names. Writes directly unless dry_run is "
        "set or the global GENECREW_DRY_RUN env var is enabled."
    )
    args_schema: type[BaseModel] = GrampsUpdateNameInput

    @api_tool(provider="GrampsWeb", endpoint="UpdateName")
    def _run(self, handle: str, dry_run: bool = False) -> str:
        # Interrupteur de sécurité GLOBAL : GENECREW_DRY_RUN=true force la simulation,
        # quel que soit le paramètre. Il ne peut que rendre l'appel PLUS sûr, jamais forcer
        # une écriture réelle (un --dry-run explicite gagne toujours vers la sécurité).
        dry_run = dry_run or os.environ.get("GENECREW_DRY_RUN", "").strip().lower() in ("1", "true", "yes")
        client = get_client()
        person = client.get_object("people", handle)
        name = person.get("primary_name") or {}
        changes = []

        # Prénom (first_name) et nom (surname_list) sont traités comme deux champs
        # DISTINCTS ; chaque changement porte son `kind` ("prénom" / "nom").
        first = name.get("first_name", "")
        if needs_normalization(first) and not is_incomplete_name(first):
            new_first = normalize_case(first)
            if new_first != first:
                if not is_case_only_change(first, new_first):
                    return err(f"gramps_update_name_case: {handle} first_name non purement de casse")
                name["first_name"] = new_first
                changes.append({"field": "first_name", "kind": "prénom",
                                "old": first, "new": new_first})

        for idx, entry in enumerate(name.get("surname_list") or []):
            surname = entry.get("surname", "")
            if not needs_normalization(surname) or is_incomplete_name(surname):
                continue
            new_surname = normalize_case(surname)
            if new_surname == surname:
                continue
            if not is_case_only_change(surname, new_surname):
                return err(f"gramps_update_name_case: {handle} surname[{idx}] non purement de casse")
            entry["surname"] = new_surname
            changes.append({"field": f"surname[{idx}]", "kind": "nom",
                            "old": surname, "new": new_surname})

        result = {"handle": handle, "gramps_id": person.get("gramps_id"),
                  "dry_run": dry_run, "changes": changes}
        if changes and not dry_run:
            client.request("PUT", f"/people/{handle}", json=person)
        return ok(result)


class GrampsUpdateGenderInput(BaseModel):
    """Input schema for GrampsUpdateGenderTool."""

    handle: str = Field(..., description="Handle of the person whose gender to set.")
    gender: int = Field(..., description="Gender integer: 0=F, 1=M, 2=U.")
    dry_run: bool = Field(False, description="If true, compute the change but do not write.")


class GrampsUpdateGenderTool(BaseTool):
    """Set a person's gender (0=F, 1=M, 2=U) in Gramps — a bounded, high-confidence fact write."""

    name: str = "gramps_update_gender"
    description: str = (
        "Sets one person's gender in Gramps (0=F, 1=M, 2=U). This writes a fact, so it is "
        "meant for high-confidence, human-authorized corrections. No-op when the gender is "
        "already the requested value. Writes directly unless dry_run is set or the global "
        "GENECREW_DRY_RUN env var is enabled."
    )
    args_schema: type[BaseModel] = GrampsUpdateGenderInput

    @api_tool(provider="GrampsWeb", endpoint="UpdateGender")
    def _run(self, handle: str, gender: int, dry_run: bool = False) -> str:
        # Interrupteur GLOBAL : GENECREW_DRY_RUN=true force la simulation (ne peut que rendre
        # l'appel PLUS sûr ; un dry_run explicite gagne toujours vers la sécurité).
        dry_run = dry_run or os.environ.get("GENECREW_DRY_RUN", "").strip().lower() in ("1", "true", "yes")
        client = get_client()
        person = client.get_object("people", handle)
        old = person.get("gender", 2)
        change = {"handle": handle, "gramps_id": person.get("gramps_id"),
                  "old": old, "new": gender, "dry_run": dry_run, "noop": False}
        if gender == old:
            change["noop"] = True
            return ok(change)
        person["gender"] = gender
        if not dry_run:
            client.request("PUT", f"/people/{handle}", json=person)
        return ok(change)
