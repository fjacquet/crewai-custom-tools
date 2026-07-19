"""Data-driven temporal transitions (sovereignty/name changes). Dataset-agnostic.

Gramps natively models dated names and dated placerefs. This module emits two
dated parent chains (before/after) + a dated alt_name WHEN a transition row
matches the resolved country. Empty dataset → single undated chain (generic).
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain, DatedName, ParsedPlace, PlaceLevel, ResolvedPlace,
)

_DATA = Path(__file__).resolve().parent.parent / "data" / "transitions.csv"
_COLS = ("modern_country", "historical_country", "historical_parent", "date")


class Transition(BaseModel):
    """One known transition: the modern country splits from a historical parent at `date`."""

    modern_country: str
    historical_country: str
    historical_parent: str
    date: str                      # ISO YYYY-MM-DD


def load_transitions() -> list[Transition]:
    """Load transitions from the embedded CSV (empty/missing → [])."""
    if not _DATA.exists():
        return []
    with _DATA.open(encoding="utf-8") as f:
        return [Transition(**{c: row[c] for c in _COLS})
                for row in csv.DictReader(f) if row.get("modern_country")]


def apply_transition(resolved: ResolvedPlace | None, parsed: ParsedPlace,
                     transitions: list[Transition]) -> ResolvedPlace | None:
    """If a transition matches `parsed.country`, split into two dated chains + dated alt_name."""
    if resolved is None:
        return resolved
    t = next((t for t in transitions if t.modern_country == parsed.country), None)
    if t is None:
        return resolved
    modern = [DatedChain(levels=c.levels, date_qualifier=f"après {t.date}")
              for c in resolved.chains] or \
             [DatedChain(levels=[PlaceLevel(name=parsed.country, place_type="Country")],
                         date_qualifier=f"après {t.date}")]
    hist_levels = [PlaceLevel(name=t.historical_parent, place_type="Country"),
                   PlaceLevel(name=t.historical_country, place_type="Region")]
    if parsed.departement:
        hist_levels.append(PlaceLevel(name=parsed.departement, place_type="Department"))
    historical = DatedChain(levels=hist_levels, date_qualifier=f"avant {t.date}")
    return resolved.model_copy(update={
        "chains": modern + [historical],
        "alt_names": [DatedName(value=parsed.raw, date_qualifier=f"avant {t.date}")],
    })
