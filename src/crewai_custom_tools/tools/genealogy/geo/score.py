"""Pure scoring for place resolution (dataset-agnostic)."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

AMBIGUITY_MARGIN = 0.10


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.strip().upper()


def similarity(a: str, b: str) -> float:
    """Accent/case-insensitive string similarity in [0,1]."""
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def fuzzy_score(provider_conf: float, asked: str, returned: str) -> float:
    """Combine provider confidence with name similarity (penalizes 'right score, wrong place')."""
    return max(0.0, min(1.0, provider_conf)) * similarity(asked, returned)


def is_ambiguous(candidates: list[float], margin: float = AMBIGUITY_MARGIN) -> bool:
    """True when the top two candidate scores are within `margin` (undecidable → proposition)."""
    if len(candidates) < 2:
        return False
    top2 = sorted(candidates, reverse=True)[:2]
    return (top2[0] - top2[1]) < margin
