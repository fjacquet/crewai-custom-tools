"""Deterministic duplicate detection (R10) — pure, stdlib only."""

from __future__ import annotations

from difflib import SequenceMatcher

from crewai_custom_tools.tools.genealogy.analysis.phonetics import normalize_name
from crewai_custom_tools.tools.genealogy.models.domain import (
    DuplicateCandidate,
    PersonFacts,
)

__all__ = ["find_duplicates", "normalize_name"]

BIRTH_YEAR_WINDOW = 2


def _key(p: PersonFacts) -> str:
    return normalize_name(f"{p.given} {p.surname}")


def find_duplicates(
    people: list[PersonFacts], threshold: float = 0.85
) -> list[DuplicateCandidate]:
    """Return candidate duplicate pairs within `people` (O(n²) over the batch)."""
    out: list[DuplicateCandidate] = []
    keyed = [(p, _key(p), p.birth.year if p.birth else None) for p in people]
    for i in range(len(keyed)):
        pa, ka, ya = keyed[i]
        if ya is None or not ka:
            continue
        for j in range(i + 1, len(keyed)):
            pb, kb, yb = keyed[j]
            if yb is None or not kb or abs(ya - yb) > BIRTH_YEAR_WINDOW:
                continue
            score = SequenceMatcher(None, ka, kb).ratio()
            if score >= threshold:
                out.append(DuplicateCandidate(
                    gramps_id_a=pa.gramps_id, gramps_id_b=pb.gramps_id,
                    score=round(score, 3),
                    reason=f"Homonymes ({ka!r} ≈ {kb!r}), naissances {ya}/{yb}."))
    return out
