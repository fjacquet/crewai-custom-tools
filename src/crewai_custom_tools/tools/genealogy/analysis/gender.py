"""Gender inference from a first name (pure, offline).

For a person of unknown sex, infer F/M from the first forename using an
INSEE+OFS births table. Gender is a FACT, not form: callers emit a Proposition
for human review — this module never writes to Gramps.
"""

from __future__ import annotations

import csv
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "prenoms_sexe.csv"
MIN_TOTAL = 50
MIN_RATIO = 0.95

_APOSTROPHES = "''ʼ"
_HYPHENS = "-‐‑‒–—"


def normkey(name: str) -> str:
    """Canonical key: uppercase, accents stripped, apostrophes/hyphens canonical.

    Shared by the runtime lookup and the build script so both index names the
    same way (INSEE is already uppercase without accents; OFS keeps accents)."""
    s = name.strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    for a in _APOSTROPHES:
        s = s.replace(a, "'")
    for h in _HYPHENS:
        s = s.replace(h, "-")
    return s


def _first_forename(given: str) -> str:
    """First forename = first space-separated segment ('Jean Baptiste' -> 'Jean')."""
    parts = given.strip().split(" ")
    return parts[0] if parts and parts[0] else ""


class GenderInference(BaseModel):
    sex: str | None                 # "M" | "F" | None (abstention)
    ratio: float                    # dominant / total (0.0 if total == 0)
    total: int                      # n_f + n_m on the chosen key
    key: str                        # key actually found ("" if none)


@lru_cache(maxsize=1)
def load_prenoms_table(path: Path = DATA_PATH) -> dict[str, tuple[int, int]]:
    """Load {normalized_key: (n_f, n_m)} from the bundled CSV (cached).

    Raises FileNotFoundError if the data file is missing (explicit failure)."""
    table: dict[str, tuple[int, int]] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            table[row["prenom"]] = (int(row["n_f"]), int(row["n_m"]))
    return table


def _counts_for(given: str, table: Mapping[str, tuple[int, int]]) -> tuple[str, tuple[int, int]]:
    """Whole first forename, then its first hyphen segment; else ('', (0, 0))."""
    key = normkey(_first_forename(given))
    if key in table:
        return key, table[key]
    if "-" in key:
        seg = key.split("-")[0]
        if seg in table:
            return seg, table[seg]
    return "", (0, 0)


def infer_sex(given: str, table: Mapping[str, tuple[int, int]]) -> GenderInference:
    """Infer F/M; abstain (sex=None) unless total >= MIN_TOTAL and ratio >= MIN_RATIO."""
    key, (n_f, n_m) = _counts_for(given, table)
    total = n_f + n_m
    if total == 0:
        return GenderInference(sex=None, ratio=0.0, total=0, key="")
    dominant = "F" if n_f >= n_m else "M"
    ratio = (n_f if dominant == "F" else n_m) / total
    sex = dominant if (total >= MIN_TOTAL and ratio >= MIN_RATIO) else None
    return GenderInference(sex=sex, ratio=ratio, total=total, key=key)
