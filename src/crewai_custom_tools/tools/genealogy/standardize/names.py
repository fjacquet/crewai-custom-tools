"""Pure French-aware name-casing normalization.

Casing is *form*, not a factual claim, so these functions never assert new
data — they only decide capitalization. The invariant `is_case_only_change`
guarantees a write can re-capitalize but never re-spell.
"""

from __future__ import annotations

# Particules abaissées quand elles forment un mot entier (français + néerlandais/allemand).
PARTICLES = frozenset({
    "de", "du", "des", "la", "le", "les",
    "von", "van", "der", "den", "ten", "ter", "zur", "zum", "y",
})


def _cap(word: str) -> str:
    """First letter upper, rest lower (single segment, no separators)."""
    return word[:1].upper() + word[1:].lower() if word else word


_APOSTROPHES = "'’ʼ"                       # ' ’ ʼ
_HYPHENS = "-‐‑‒–—"         # - ‐ ‑ ‒ – —


def _recase_token(token: str) -> str:
    """Recase one space-delimited token, handling hyphen and apostrophe variants
    (ASCII and common Unicode), preserving the exact separator character."""
    for hyphen in _HYPHENS:
        if hyphen in token:
            return hyphen.join(_recase_token(part) for part in token.split(hyphen))
    for apo in _APOSTROPHES:
        if apo in token:
            prefix, _, rest = token.partition(apo)
            if prefix.lower() in ("d", "l"):          # particule élidée d'/l'
                return prefix.lower() + apo + _recase_token(rest)
            return _cap(prefix) + apo + _recase_token(rest)   # O'Brien
    return _cap(token)


def normalize_case(name: str) -> str:
    """Return `name` with French-aware title casing."""
    out = []
    for word in name.split():
        out.append(word.lower() if word.lower() in PARTICLES else _recase_token(word))
    return " ".join(out)


def needs_normalization(name: str) -> bool:
    """True only when `name`'s letters are all upper or all lower (import artifacts)."""
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return False
    return all(c.isupper() for c in letters) or all(c.islower() for c in letters)


def is_case_only_change(old: str, new: str) -> bool:
    """The safety invariant: `new` differs from `old` only by capitalization."""
    return old.casefold() == new.casefold()


def is_incomplete_name(name: str) -> bool:
    """True if the name carries a placeholder '?' or a digit (incomplete fact)."""
    return "?" in name or any(c.isdigit() for c in name)
