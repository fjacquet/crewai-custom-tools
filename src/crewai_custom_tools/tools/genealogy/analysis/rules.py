"""Pure deterministic genealogy consistency rules (R1–R9).

Every function is side-effect free: it takes normalized facts and returns
Anomaly objects. Date comparisons use the Gramps Julian-day `sortval`
(integer); a rule is skipped when the dates it needs are unknown (sortval 0),
so unknown data never produces a false positive.
"""

from __future__ import annotations

from crewai_custom_tools.tools.genealogy.models.domain import (
    Anomaly,
    FamilyFacts,
    PersonFacts,
)

DAYS_PER_YEAR = 365.25
POSTMORTEM_TYPES = {"Burial", "Cremation", "Probate", "Will"}


def is_valid(ev) -> bool:
    """True when the event exists and carries a sortable date."""
    return ev is not None and ev.sortval > 0


def years_between(a, b) -> float:
    """Signed years from a to b using sortval (both must be valid)."""
    return (b.sortval - a.sortval) / DAYS_PER_YEAR


def _anom(rule, severity, p: PersonFacts, message, **detail) -> Anomaly:
    return Anomaly(rule=rule, severity=severity, gramps_id=p.gramps_id,
                   handle=p.handle, message=message, detail=detail)


def check_person(person: PersonFacts) -> list[Anomaly]:
    """Run all person-scoped rules (R1, R2, R6, R7, R8, R9)."""
    out: list[Anomaly] = []
    b, d = person.birth, person.death

    # R1 — birth after death
    if is_valid(b) and is_valid(d) and b.sortval > d.sortval:
        out.append(_anom("R1", "haute", person,
                         "Naissance postérieure au décès.",
                         birth_year=b.year, death_year=d.year))

    # R2 — age at death > 105
    if is_valid(b) and is_valid(d):
        age = years_between(b, d)
        if age > 105:
            out.append(_anom("R2", "haute", person,
                             f"Âge au décès de {age:.0f} ans (> 105).",
                             birth_year=b.year, death_year=d.year, age=round(age, 1)))

    # R6 — life event outside the person's lifespan
    for ev in person.events:
        if ev.type in POSTMORTEM_TYPES or ev.type in {"Birth", "Death"}:
            continue
        if not is_valid(ev):
            continue
        if is_valid(b) and ev.sortval < b.sortval:
            out.append(_anom("R6", "moyenne", person,
                             f"Événement « {ev.type} » ({ev.year}) daté avant la naissance.",
                             event_type=ev.type, event_year=ev.year, birth_year=b.year))
        elif is_valid(d) and ev.sortval > d.sortval:
            out.append(_anom("R6", "moyenne", person,
                             f"Événement « {ev.type} » ({ev.year}) daté après le décès.",
                             event_type=ev.type, event_year=ev.year, death_year=d.year))

    # R7 — baptism before birth ; burial before death
    for ev in person.events:
        if ev.type == "Baptism" and is_valid(ev) and is_valid(b) and ev.sortval < b.sortval:
            out.append(_anom("R7", "moyenne", person,
                             "Baptême antérieur à la naissance.",
                             baptism_year=ev.year, birth_year=b.year))
        if ev.type == "Burial" and is_valid(ev) and is_valid(d) and ev.sortval < d.sortval:
            out.append(_anom("R7", "moyenne", person,
                             "Inhumation antérieure au décès.",
                             burial_year=ev.year, death_year=d.year))

    # R8 — malformed date
    for ev in person.events:
        has_date = bool(ev.dateval) or ev.year is not None
        out_of_bounds = (len(ev.dateval) >= 2
                         and isinstance(ev.dateval[0], int) and isinstance(ev.dateval[1], int)
                         and (ev.dateval[0] > 31 or ev.dateval[1] > 12))
        if out_of_bounds or (has_date and ev.sortval == 0):
            out.append(_anom("R8", "basse", person,
                             f"Date malformée ou non interprétable sur « {ev.type} ».",
                             event_type=ev.type, dateval=ev.dateval))

    # R9 — no source at all
    if not person.has_any_citation:
        out.append(_anom("R9", "basse", person,
                         "Aucune source ni citation rattachée."))

    return out
