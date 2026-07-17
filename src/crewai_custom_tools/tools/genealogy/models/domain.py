"""Hand-written domain models for the deterministic audit (Phase 1a).

These are the normalized facts the pure rules operate on — decoupled from the
raw Gramps Web JSON, which the genecrew orchestrator maps into these shapes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventFact(BaseModel):
    """One dated event, reduced to what the rules need."""

    type: str                       # "Birth", "Death", "Baptism", "Burial", "Marriage"...
    sortval: int = 0                # Julian day number; 0 = unknown/unsortable
    year: int | None = None
    modifier: int = 0               # 0 exact,1 before,2 after,3 about,4 range,5 span,6 text
    quality: int = 0                # 0 normal,1 estimated,2 calculated
    dateval: list = Field(default_factory=list)
    has_citation: bool = False


class PersonFacts(BaseModel):
    """Normalized person facts for the rules engine."""

    gramps_id: str
    handle: str
    name: str
    surname: str
    given: str
    sex: str                        # "M", "F", "U"
    birth: EventFact | None = None
    death: EventFact | None = None
    events: list[EventFact] = Field(default_factory=list)
    has_any_citation: bool = False
    parent_family_handles: list[str] = Field(default_factory=list)
    family_handles: list[str] = Field(default_factory=list)


class FamilyFacts(BaseModel):
    """Normalized family facts for the family rules (R3, R4, R5)."""

    gramps_id: str
    handle: str
    father_handle: str | None = None
    mother_handle: str | None = None
    child_handles: list[str] = Field(default_factory=list)
    marriage: EventFact | None = None


class Anomaly(BaseModel):
    """One detected inconsistency, attached to a person."""

    rule: str                       # "R1".."R9"
    severity: str                   # "haute" | "moyenne" | "basse"
    gramps_id: str
    handle: str
    message: str                    # human-readable, French
    detail: dict = Field(default_factory=dict)


class DuplicateCandidate(BaseModel):
    """A pair of persons that may be duplicates (R10)."""

    gramps_id_a: str
    gramps_id_b: str
    score: float
    reason: str
