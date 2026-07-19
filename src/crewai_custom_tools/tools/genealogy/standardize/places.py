"""Pure parsing of flat GEDCOM-style place strings + country normalization.

A GEDCOM place is comma-delimited, most-specific first, country last. Import
tools (Geneanet/Heredis) often embed an INSEE code. This module is dataset-
agnostic: it reads positions and known-code shapes, it does not hardcode any
particular tree.
"""

from __future__ import annotations

import re
import unicodedata

from crewai_custom_tools.tools.genealogy.models.domain import ParsedPlace

CORSICA_RE = re.compile(r"^2[AB]\d{3}$")             # 2A004 : unambiguously INSEE
FIVE_DIGIT_RE = re.compile(r"^\d{5}$")               # 18033 or 18000 : INSEE or postal, ambiguous alone
POSTAL_RE = re.compile(r"^\d{4,5}$")

# Table de normalisation des pays : variantes (casse/langue/accent/parasite) → label FR.
_COUNTRY = {
    "france": "France",
    "suisse": "Suisse", "switzerland": "Suisse", "schweiz": "Suisse",
    "allemagne": "Allemagne", "germany": "Allemagne", "deutschland": "Allemagne",
    "italie": "Italie", "italia": "Italie", "italy": "Italie",
    "algerie": "Algérie", "algerie francaise": "Algérie", "algeria": "Algérie",
    "belgique": "Belgique", "belgium": "Belgique",
    "pologne": "Pologne", "poland": "Pologne",
    "etats-unis": "États-Unis", "usa": "États-Unis", "united states": "États-Unis",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_country(raw: str) -> str:
    """Map a messy country segment to a canonical French label ('' if empty/unknown)."""
    key = _strip_accents(raw).strip().strip(">").strip().lower()
    if not key:
        return ""
    return _COUNTRY.get(key, raw.strip().strip(">").strip())


def parse_pname(raw: str) -> ParsedPlace:
    """Parse one flat place string into ParsedPlace (positional + code detection)."""
    segments = [s.strip() for s in raw.split(",")]
    nonempty_idx = [i for i, s in enumerate(segments) if s]
    country_idx = nonempty_idx[-1] if nonempty_idx else None
    country = normalize_country(segments[country_idx]) if country_idx is not None else ""

    # Code detection: a Corsica-shaped segment (2A/2B + 3 digits) is unambiguously INSEE.
    # A plain 5-digit segment is ambiguous alone (postal codes are also 5 digits) — only
    # trust it as INSEE when a second plain 5-digit segment is present (Geneanet order:
    # INSEE then postal). With exactly one, treat it as the postal and leave insee unset
    # so France falls through to fuzzy resolution instead of a wrong authoritative write.
    corsica_idx = next((i for i, s in enumerate(segments) if CORSICA_RE.match(s)), None)
    five_digit_idx = [i for i, s in enumerate(segments) if FIVE_DIGIT_RE.match(s)]
    if corsica_idx is not None:
        insee_idx = corsica_idx
    elif len(five_digit_idx) >= 2:
        insee_idx = five_digit_idx[0]
    else:
        insee_idx = None
    insee = segments[insee_idx] if insee_idx is not None else None
    postal_idx = next((i for i, s in enumerate(segments)
                       if i != insee_idx and POSTAL_RE.match(s)), None)
    postal = segments[postal_idx] if postal_idx is not None else None

    # Commune = segment before the INSEE code; else first non-empty segment that is
    # neither the country position nor a bare code.
    if insee_idx is not None and insee_idx > 0:
        commune = segments[insee_idx - 1]
        commune_idx = insee_idx - 1
    else:
        commune, commune_idx = "", None
        for i in nonempty_idx:
            if i == country_idx or POSTAL_RE.match(segments[i]):
                continue
            commune, commune_idx = segments[i], i
            break

    # Département / région = remaining non-empty segments, excluded BY INDEX (not value).
    used = {country_idx, insee_idx, postal_idx, commune_idx}
    tail = [segments[i] for i in nonempty_idx if i not in used]
    departement = tail[0] if len(tail) >= 1 else ""
    region = tail[1] if len(tail) >= 2 else ""

    shifted = country == "France" and insee is None
    return ParsedPlace(raw=raw, commune=commune, insee=insee, postal=postal,
                       departement=departement, region=region, country=country, shifted=shifted)
