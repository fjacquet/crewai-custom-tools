"""Germany resolver: authoritative AGS / (name, Land) -> embedded BKG VG250 gazetteer.

German genealogy place strings often carry the 8-digit AGS (Amtlicher Gemeindeschlüssel),
a unique official municipality key. When present it resolves authoritatively; otherwise the
commune name is looked up, narrowed by the Land when the string carries one (homonyms like
Waldeck in Hesse vs. Thuringia otherwise stay a proposition).
"""
from __future__ import annotations

import csv
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain,
    DatedName,
    ParsedPlace,
    PlaceLevel,
    ResolvedPlace,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "de_communes.csv"
_SOURCE = "BKG VG250"
_UMLAUT = {"ß": "ss", "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}


def _norm_de(s: str) -> str:
    """German-aware key: expand ß/umlauts BEFORE stripping accents, then upper/trim."""
    for k, v in _UMLAUT.items():
        s = s.replace(k, v)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.strip().upper()


# Land canon : variantes FR/EN/DE normalisées -> Land allemand canonique normalisé.
_LAND_ALIASES = {
    "Baden-Württemberg": ["Bade-Wurtemberg", "Baden-Wurttemberg"], "Bayern": ["Bavière", "Bavaria"],
    "Berlin": [], "Brandenburg": ["Brandebourg"], "Bremen": ["Brême"], "Hamburg": ["Hambourg"],
    "Hessen": ["Hesse"], "Mecklenburg-Vorpommern": ["Mecklembourg-Poméranie"],
    "Niedersachsen": ["Basse-Saxe", "Lower Saxony"],
    "Nordrhein-Westfalen": ["Rhénanie-du-Nord-Westphalie"],
    "Rheinland-Pfalz": ["Rhénanie-Palatinat"], "Saarland": ["Sarre"], "Sachsen": ["Saxe", "Saxony"],
    "Sachsen-Anhalt": ["Saxe-Anhalt"], "Schleswig-Holstein": [],
    "Thüringen": ["Thuringe", "Thuringia"],
}
_LAND_CANON: dict[str, str] = {}
for _canon, _aliases in _LAND_ALIASES.items():
    _LAND_CANON[_norm_de(_canon)] = _norm_de(_canon)
    for _a in _aliases:
        _LAND_CANON[_norm_de(_a)] = _norm_de(_canon)


def _land_canon(s: str) -> str | None:
    return _LAND_CANON.get(_norm_de(s)) if s else None


@lru_cache(maxsize=1)
def load_de_gazetteer(path: Path = DATA_PATH) -> dict:
    by_ags: dict[str, dict] = {}
    by_name: dict[str, list] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_ags[row["ags"]] = row
            by_name[_norm_de(row["name"])].append(row)
    return {"by_ags": by_ags, "by_name": dict(by_name)}


def _build(entry: dict, parsed: ParsedPlace, *, ambiguous: bool) -> ResolvedPlace:
    return ResolvedPlace(
        name=entry["name"], place_type="Municipality",
        lat=str(entry["lat"]), long=str(entry["long"]), code=entry["ags"],
        chains=[DatedChain(levels=[PlaceLevel(name="Allemagne", place_type="Country"),
                                   PlaceLevel(name=entry["land"], place_type="State")])],
        alt_names=[DatedName(value=parsed.raw)],
        score=1.0, ambiguous=ambiguous,
        source=_SOURCE + (" (homonymes)" if ambiguous else ""), query=entry["ags"],
    )


def resolve_de(parsed: ParsedPlace, table: dict | None = None) -> ResolvedPlace | None:
    """AGS -> authoritative ; (name, Land) unique -> authoritative ; homonyms -> proposition."""
    table = table if table is not None else load_de_gazetteer()
    if parsed.ags and parsed.ags in table["by_ags"]:
        return _build(table["by_ags"][parsed.ags], parsed, ambiguous=False)
    if not parsed.commune:
        return None
    candidates = table["by_name"].get(_norm_de(parsed.commune), [])
    if not candidates:
        return None
    land = next((_land_canon(x) for x in (parsed.region, parsed.departement) if _land_canon(x)), None)
    if land and len(candidates) > 1:
        narrowed = [c for c in candidates if _land_canon(c["land"]) == land]
        if narrowed:
            candidates = narrowed
    return _build(candidates[0], parsed, ambiguous=len(candidates) > 1)
