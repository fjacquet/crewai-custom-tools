"""Write-side CrewAI tools over the Gramps Web API.

First writer in the genealogy domain. GrampsUpdateNameTool re-capitalizes a
person's primary name in place and refuses any change that is not purely a
casing change (the invariant), so it can never re-spell a name.
"""

import logging
import os
import uuid

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

_DRY_RUN_TRUE = ("1", "true", "yes")


def effective_dry_run(dry_run: bool) -> bool:
    """True when writes must be simulated: the explicit param OR the global switch.

    `GENECREW_DRY_RUN` is a safety switch that can only *force* simulation (an explicit
    `dry_run=True` always wins toward safety). When the variable is **absent**, the safe
    default is to SIMULATE — never silently write. Set `GENECREW_DRY_RUN=false` to write
    for real.
    """
    return dry_run or os.environ.get("GENECREW_DRY_RUN", "true").strip().lower() in _DRY_RUN_TRUE


_DATE_MODIFIER = {"avant": 1, "après": 2, "apres": 2}


def date_qualifier_to_gramps_date(qualifier: str | None) -> dict | None:
    """Convert 'avant/après YYYY-MM-DD' into a Gramps Date object (None if unrecognized)."""
    if not qualifier:
        return None
    word, _, iso = qualifier.partition(" ")
    modifier = _DATE_MODIFIER.get(word.strip().lower())
    if modifier is None:
        return None
    try:
        year, month, day = (int(x) for x in iso.strip().split("-"))
    except ValueError:
        return None
    return {"_class": "Date", "modifier": modifier, "dateval": [day, month, year, False]}


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
        dry_run = effective_dry_run(dry_run)
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
        dry_run = effective_dry_run(dry_run)
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


def _created_handle(data) -> str | None:
    """Extract the created object's handle from a Gramps Web POST response.

    POST /api/places/ returns a 201 *transaction array* (e.g. [{"type": "add",
    "_class": "Place", "handle": "...", "new": {...}}]), not a bare dict — so we
    scan the items for a top-level (or nested "new") handle.
    """
    items = data if isinstance(data, list) else [data]
    for item in items:
        if isinstance(item, dict):
            if item.get("handle"):
                return item["handle"]
            new = item.get("new")
            if isinstance(new, dict) and new.get("handle"):
                return new["handle"]
    return None


class GrampsCreatePlaceInput(BaseModel):
    name: str = Field(..., description="Place name value.")
    place_type: str = Field(..., description="Gramps place type (Country, Region, Department…).")
    parent_handle: str | None = Field(None, description="Handle of the parent place, if any.")
    date_qualifier: str | None = Field(None, description="Optional placeref date qualifier.")
    lat: str | None = Field(None, description="WGS84 latitude decimal string.")
    long: str | None = Field(None, description="WGS84 longitude decimal string.")
    code: str | None = Field(None, description="Place code (INSEE/OFS/postal).")
    dry_run: bool = Field(False, description="If true, simulate and return a synthetic handle.")


class GrampsCreatePlaceTool(BaseTool):
    """Create a parent/leaf place. Returns its handle (synthetic 'DRYRUN:<name>' in dry-run)."""

    name: str = "gramps_create_place"
    description: str = (
        "Creates a Gramps place with an optional parent (placeref). Returns the new handle. "
        "In dry-run (flag or GENECREW_DRY_RUN) it POSTs nothing and returns 'DRYRUN:<name>'."
    )
    args_schema: type[BaseModel] = GrampsCreatePlaceInput

    @api_tool(provider="GrampsWeb", endpoint="CreatePlace")
    def _run(self, name, place_type, parent_handle=None, date_qualifier=None,
             lat=None, long=None, code=None, dry_run=False) -> str:
        dry_run = effective_dry_run(dry_run)
        placeref_list = []
        if parent_handle:
            ref = {"ref": parent_handle}
            gdate = date_qualifier_to_gramps_date(date_qualifier)
            if gdate is not None:
                ref["date"] = gdate
            placeref_list.append(ref)
        gen_handle = uuid.uuid4().hex
        payload = {"_class": "Place", "handle": gen_handle, "name": {"value": name},
                   "place_type": place_type, "placeref_list": placeref_list}
        if lat:
            payload["lat"] = lat
        if long:
            payload["long"] = long
        if code:
            payload["code"] = code
        if dry_run:
            return ok({"handle": f"DRYRUN:{name}", "dry_run": True, "created": False})
        resp = get_client().request("POST", "/places/", json=payload)
        data = resp.json() if resp.content else None
        # Gramps Web returns a 201 transaction ARRAY (not a dict); take the created
        # place's handle from it, falling back to the client-generated handle we sent.
        handle = _created_handle(data) or gen_handle
        return ok({"handle": handle, "dry_run": False, "created": True})


class GrampsUpdatePlaceInput(BaseModel):
    handle: str = Field(..., description="Handle of the existing place to enrich.")
    name: str = Field(..., description="Canonical modern name value.")
    place_type: str = Field(..., description="Gramps place type.")
    lat: str | None = Field(None, description="WGS84 latitude.")
    long: str | None = Field(None, description="WGS84 longitude.")
    code: str | None = Field(None, description="Place code.")
    placeref_list: list | None = Field(None, description="Parent placerefs [{ref, ...}].")
    alt_names: list | None = Field(None, description="Alt names [{value, ...}] to add if absent.")
    provenance: str | None = Field(None, description="Provenance string for a note (informational).")
    dry_run: bool = Field(False, description="If true, compute changes but do not write.")


class GrampsUpdatePlaceTool(BaseTool):
    """Enrich an existing place in place (name/type/GPS/placerefs/alt_names). No-op when conforming."""

    name: str = "gramps_update_place"
    description: str = (
        "Enriches one existing Gramps place: canonical name, type, WGS84 lat/long, parent "
        "placerefs, and adds alt_names if absent. No-op when already conforming. Writes "
        "directly unless dry_run is set or GENECREW_DRY_RUN is enabled."
    )
    args_schema: type[BaseModel] = GrampsUpdatePlaceInput

    @api_tool(provider="GrampsWeb", endpoint="UpdatePlace")
    def _run(self, handle, name, place_type, lat=None, long=None, code=None,
             placeref_list=None, alt_names=None, provenance=None, dry_run=False) -> str:
        dry_run = effective_dry_run(dry_run)
        place = get_client().get_object("places", handle)
        before = {"name": (place.get("name") or {}).get("value"),
                  "place_type": place.get("place_type"), "lat": place.get("lat"),
                  "long": place.get("long"), "code": place.get("code"),
                  "placeref_list": place.get("placeref_list") or []}
        place["name"] = {**(place.get("name") or {}), "value": name}
        place["place_type"] = place_type
        if lat is not None:
            place["lat"] = lat
        if long is not None:
            place["long"] = long
        if code is not None:
            place["code"] = code
        if placeref_list is not None:
            normalized = []
            for ref in placeref_list:
                ref = dict(ref)
                gdate = date_qualifier_to_gramps_date(ref.pop("_date_qualifier", None))
                if gdate is not None:
                    ref["date"] = gdate
                normalized.append(ref)
            place["placeref_list"] = normalized
        existing_alt = place.get("alt_names") or []
        existing_values = {a.get("value") for a in existing_alt}
        original_values = set(existing_values)
        for a in (alt_names or []):
            if a.get("value") not in existing_values:
                existing_alt.append(a)
                existing_values.add(a.get("value"))
        place["alt_names"] = existing_alt
        after = {"name": name, "place_type": place_type, "lat": lat if lat is not None else place.get("lat"),
                 "long": long if long is not None else place.get("long"),
                 "code": code if code is not None else place.get("code"),
                 "placeref_list": placeref_list if placeref_list is not None else before["placeref_list"]}
        noop = before == after and original_values >= {a.get("value") for a in (alt_names or [])}
        change = {"handle": handle, "gramps_id": place.get("gramps_id"),
                  "dry_run": dry_run, "noop": noop}
        if not noop and not dry_run:
            get_client().request("PUT", f"/places/{handle}", json=place)
        return ok(change)


class GrampsMergePlacesInput(BaseModel):
    keep_handle: str = Field(..., description="Handle of the surviving place (phoenix).")
    merge_handle: str = Field(..., description="Handle of the place absorbed then deleted (titanic).")
    dry_run: bool = Field(False, description="If true, simulate without merging.")


class GrampsMergePlacesTool(BaseTool):
    """Merge two places (moves backlinks). Human-triggered only; never called automatically."""

    name: str = "gramps_merge_places"
    description: str = (
        "Merges the 'merge' place into the 'keep' place in Gramps (migrates event backlinks, "
        "then removes the duplicate). Writes unless dry_run is set or GENECREW_DRY_RUN is enabled."
    )
    args_schema: type[BaseModel] = GrampsMergePlacesInput

    @api_tool(provider="GrampsWeb", endpoint="MergePlaces")
    def _run(self, keep_handle: str, merge_handle: str, dry_run: bool = False) -> str:
        dry_run = effective_dry_run(dry_run)
        change = {"keep": keep_handle, "merge": merge_handle, "dry_run": dry_run}
        if not dry_run:
            get_client().request("POST", f"/places/{keep_handle}/merge/{merge_handle}")
        return ok(change)


# --- Écriture encadrée append-only pour la crew : notes + tags (seul le Chroniqueur les a) ---


class GrampsCreateNoteInput(BaseModel):
    text: str = Field(..., description="Note body text (plain string).")
    note_type: str = Field("Research", description="Gramps note type string (e.g. 'Research').")
    dry_run: bool = Field(False, description="If true, POST nothing and return a synthetic handle.")


class GrampsCreateNoteTool(BaseTool):
    """Create a Gramps note (append-only annotation). Returns its handle (synthetic in dry-run)."""

    name: str = "gramps_create_note"
    description: str = (
        "Creates a Gramps note carrying free text (e.g. an audit finding marked "
        "'[genecrew:audit:<date>:detective]'). Returns the new note handle. In dry-run (flag or "
        "GENECREW_DRY_RUN) it POSTs nothing and returns 'DRYRUN:note'."
    )
    args_schema: type[BaseModel] = GrampsCreateNoteInput

    @api_tool(provider="GrampsWeb", endpoint="CreateNote")
    def _run(self, text: str, note_type: str = "Research", dry_run: bool = False) -> str:
        dry_run = effective_dry_run(dry_run)
        gen_handle = uuid.uuid4().hex
        payload = {"_class": "Note", "handle": gen_handle, "type": note_type,
                   "text": {"_class": "StyledText", "string": text, "tags": []}}
        if dry_run:
            return ok({"handle": "DRYRUN:note", "dry_run": True, "created": False})
        resp = get_client().request("POST", "/notes/", json=payload)
        data = resp.json() if resp.content else None
        return ok({"handle": _created_handle(data) or gen_handle, "dry_run": False, "created": True})


class GrampsEnsureTagInput(BaseModel):
    name: str = Field(..., description="Tag name, e.g. 'ia-anomalie' or 'ia-a-verifier'.")
    color: str = Field("#FF0000", description="Hex color used only when creating the tag.")
    priority: int = Field(0, description="Priority used only when creating the tag.")
    dry_run: bool = Field(False, description="If true, do not create; return 'DRYRUN:tag' if absent.")


class GrampsEnsureTagTool(BaseTool):
    """Ensure a tag exists by name (idempotent). Returns its handle (existing or created)."""

    name: str = "gramps_ensure_tag"
    description: str = (
        "Returns the handle of the tag named `name`, creating it only if it does not already "
        "exist (idempotent — never creates a duplicate). In dry-run, an absent tag yields "
        "'DRYRUN:tag' instead of being created."
    )
    args_schema: type[BaseModel] = GrampsEnsureTagInput

    @api_tool(provider="GrampsWeb", endpoint="EnsureTag")
    def _run(self, name: str, color: str = "#FF0000", priority: int = 0,
             dry_run: bool = False) -> str:
        dry_run = effective_dry_run(dry_run)
        client = get_client()
        for tag in client.get_json("/tags/") or []:
            if isinstance(tag, dict) and tag.get("name") == name:
                return ok({"handle": tag.get("handle"), "created": False, "dry_run": dry_run})
        if dry_run:
            return ok({"handle": "DRYRUN:tag", "created": False, "dry_run": True})
        gen_handle = uuid.uuid4().hex
        payload = {"_class": "Tag", "handle": gen_handle, "name": name,
                   "color": color, "priority": priority}
        resp = client.request("POST", "/tags/", json=payload)
        data = resp.json() if resp.content else None
        return ok({"handle": _created_handle(data) or gen_handle, "created": True, "dry_run": False})


class GrampsAttachInput(BaseModel):
    handle: str = Field(..., description="Handle of the person to annotate.")
    note_handle: str = Field("", description="Note handle to append to note_list (empty = none).")
    tag_handle: str = Field("", description="Tag handle to append to tag_list (empty = none).")
    dry_run: bool = Field(False, description="If true, compute the change but do not PUT.")


class GrampsAttachTool(BaseTool):
    """Append-only: attach a note and/or tag to a person. Touches ONLY note_list / tag_list."""

    name: str = "gramps_attach"
    description: str = (
        "Attaches an existing note and/or tag to a person by appending their handles to the "
        "person's note_list / tag_list (deduplicated). Append-only: it changes nothing else, and "
        "skips a handle already present or synthetic ('DRYRUN:'). Writes unless dry_run or "
        "GENECREW_DRY_RUN."
    )
    args_schema: type[BaseModel] = GrampsAttachInput

    @api_tool(provider="GrampsWeb", endpoint="Attach")
    def _run(self, handle: str, note_handle: str | None = None,
             tag_handle: str | None = None, dry_run: bool = False) -> str:
        dry_run = effective_dry_run(dry_run)
        client = get_client()
        person = client.get_object("people", handle)
        note_list = list(person.get("note_list") or [])
        tag_list = list(person.get("tag_list") or [])
        added = {"note": None, "tag": None}
        if (note_handle and not str(note_handle).startswith("DRYRUN:")
                and note_handle not in note_list):
            note_list.append(note_handle)
            added["note"] = note_handle
        if (tag_handle and not str(tag_handle).startswith("DRYRUN:")
                and tag_handle not in tag_list):
            tag_list.append(tag_handle)
            added["tag"] = tag_handle
        changed = added["note"] is not None or added["tag"] is not None
        result = {"handle": handle, "gramps_id": person.get("gramps_id"),
                  "added": added, "changed": changed, "dry_run": dry_run}
        if changed and not dry_run:
            # Append-only strict : on repart de l'objet complet et on ne réaffecte QUE les deux
            # listes ; tout autre champ reste identique (aucune donnée cœur touchée).
            updated = dict(person)
            updated["note_list"] = note_list
            updated["tag_list"] = tag_list
            client.request("PUT", f"/people/{handle}", json=updated)
        return ok(result)
