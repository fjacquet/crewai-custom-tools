"""US resolver: authoritative name+state → US Census Gazetteer Places table.

US genealogy place strings carry no embedded code (unlike French INSEE), so
resolution is by (city name, state) — the state parsed out of the raw string,
the city/FIPS/coordinates looked up in the embedded, offline Census
Gazetteer table (the INSEE-analog for the US).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from crewai_custom_tools.tools.genealogy.analysis.gender import normkey
from crewai_custom_tools.tools.genealogy.geo.score import fuzzy_score
from crewai_custom_tools.tools.genealogy.models.domain import (
    DatedChain, DatedName, ParsedPlace, PlaceLevel, ResolvedPlace,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "us_places.csv"
_SOURCE = "US Census Gazetteer"

# 50 states + DC + PR, proper-cased full name -> USPS code.
_STATE_NAMES: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC", "Puerto Rico": "PR",
}
_USPS_TO_FULL: dict[str, str] = {usps: name for name, usps in _STATE_NAMES.items()}

# Lookup used to parse a state out of a raw place string: full name (lowercased)
# AND 2-letter abbreviation (lowercased) -> USPS code.
_STATES: dict[str, str] = {}
for _name, _usps in _STATE_NAMES.items():
    _STATES[_name.lower()] = _usps
    _STATES[_usps.lower()] = _usps

# The Census Gazetteer's NAME field carries a trailing legal/statistical area
# descriptor ("Springfield city", "Elm Grove CDP", "Georgetown town") that a
# genealogy string's bare commune name ("Springfield") never does. Stripped
# only when building/probing the LOOKUP key — entry["name"] (and ResolvedPlace
# .name) always keeps the full official Census form.
_LSAD_SUFFIXES = (
    "consolidated government", "metropolitan government", "unified government",
    "municipality", "corporation", "township", "borough", "village",
    "town", "city", "CDP",
)


def _lookup_key(name: str) -> str:
    """normkey(name) with one trailing Census LSAD suffix stripped, if present."""
    key = normkey(name)
    for suffix in _LSAD_SUFFIXES:
        suffix_key = normkey(suffix)
        if key.endswith(" " + suffix_key):
            return key[: -(len(suffix_key) + 1)]
    return key


def _display_bare_name(name: str) -> str:
    """Same suffix strip as `_lookup_key`, but case/spacing-preserving (for scoring).

    A (name, state) key match against this authoritative table is an exact
    identity match — the LSAD suffix ("city"/"town"/"CDP"...) is a naming
    convention, not evidence of a fuzzier match, so it must not deflate the
    score used to compare against `parsed.commune`.
    """
    lowered = name.lower()
    for suffix in _LSAD_SUFFIXES:
        suffix_lower = suffix.lower()
        if lowered.endswith(" " + suffix_lower):
            return name[: -(len(suffix_lower) + 1)]
    return name


@lru_cache(maxsize=1)
def load_us_gazetteer(path: Path = DATA_PATH) -> dict[tuple[str, str], dict]:
    """Load {(lookup_key(name), state_usps): {"name","geoid","lat","long"}} (cached).

    Raises FileNotFoundError if the data file is missing (explicit failure).
    Callers must not mutate the returned dict (shared, cached instance).
    """
    table: dict[tuple[str, str], dict] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (_lookup_key(row["name"]), row["state"].strip().upper())
            table[key] = {
                "name": row["name"],
                "geoid": row["geoid"],
                "lat": row["lat"],
                "long": row["long"],
            }
    return table


def _find_state(raw: str) -> str | None:
    """Scan comma-separated tokens of a raw place string for a US state (full name or abbr)."""
    for token in raw.split(","):
        key = token.strip().lower()
        if key in _STATES:
            return _STATES[key]
    return None


def resolve_us(parsed: ParsedPlace, table: dict | None = None) -> ResolvedPlace | None:
    """Resolve a US place by (city name, state) via the embedded Census Gazetteer.

    None when no US state token is found in `parsed.raw`, or when the
    (name, state) pair isn't in the table — the registry then falls back to
    Nominatim (worldwide fuzzy resolution).
    """
    if table is None:
        table = load_us_gazetteer()
    state = _find_state(parsed.raw)
    if state is None:
        return None
    entry = table.get((_lookup_key(parsed.commune), state))
    if entry is None:
        return None

    levels = [
        PlaceLevel(name="États-Unis", place_type="Country"),
        PlaceLevel(name=_USPS_TO_FULL.get(state, state), place_type="State"),
    ]
    if parsed.departement:
        levels.append(PlaceLevel(name=parsed.departement, place_type="County"))

    return ResolvedPlace(
        name=entry["name"], place_type="City",
        lat=entry["lat"], long=entry["long"], code=entry["geoid"],
        chains=[DatedChain(levels=levels)],
        alt_names=[DatedName(value=parsed.raw)],
        score=fuzzy_score(1.0, parsed.commune, _display_bare_name(entry["name"])),
        ambiguous=False,          # a resolved state narrows the lookup to one key
        source=_SOURCE, query=f"{parsed.commune}, {state}",
    )
