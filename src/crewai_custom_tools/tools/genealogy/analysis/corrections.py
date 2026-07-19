"""D-rules: pure correction detectors that turn family context into propositions.

Born from the LLM crew's two validated finds (I0010, I2002) — the deduction was
mechanizable, so it becomes free deterministic Python. Each detector returns a
PropositionAudit (human-reviewed, never auto-written) or None.
"""

from __future__ import annotations

from crewai_custom_tools.tools.genealogy.analysis.rules import is_valid
from crewai_custom_tools.tools.genealogy.models.domain import (
    FamilyFacts,
    PersonFacts,
    PropositionAudit,
)

# Fenêtre parentale plausible pour la correction de siècle (bornes R3 resserrées).
_PARENT_MIN_AGE = 15
_PARENT_MAX_AGE = 60
_SIBLING_WINDOW = 25  # ans autour de la fratrie datée
_CENTURY = 100


def suggest_misattached_parent_event(
    person: PersonFacts, parent_families: list[FamilyFacts],
) -> PropositionAudit | None:
    """D-mariage-des-parents: an event of the person, dated before their birth, whose
    sortval equals a parent family's marriage — almost certainly the parents' marriage
    attached to the child (cas I0010). Pure."""
    if not is_valid(person.birth):
        return None
    for event in person.events:
        if event.type in {"Birth", "Death"} or not is_valid(event):
            continue
        if event.sortval >= person.birth.sortval:
            continue
        for family in parent_families:
            if not is_valid(family.marriage):
                continue
            if event.sortval == family.marriage.sortval:
                return PropositionAudit(
                    type="relation", gramps_id=person.gramps_id, handle=person.handle,
                    personne=person.name,
                    cible=f"événement {event.type} ({event.year}) de {person.gramps_id}",
                    action=f"Détacher l'événement {event.type} daté de {event.year} de "
                           f"{person.name} : il est antérieur à sa naissance "
                           f"({person.birth.year}) et sa date coïncide exactement avec le "
                           f"mariage de la famille parentale {family.gramps_id} — le "
                           f"rattacher à cette famille.",
                    preuve_detail=f"sortval identique à la journée près entre l'événement "
                                  f"et le mariage de {family.gramps_id} ; événement "
                                  f"antérieur à la naissance. Données internes Gramps.",
                    priorite="moyenne", confiance=2)
    return None


def _century_fixed_ok(person_year: int, parent: PersonFacts | None) -> bool:
    """After -100y, is the parent plausibly alive and of childbearing age? Pure."""
    if parent is None or not is_valid(parent.birth) or parent.birth.year is None:
        return True                                  # parent non daté: pas d'objection
    fixed = person_year - _CENTURY
    age = fixed - parent.birth.year
    if not (_PARENT_MIN_AGE <= age <= _PARENT_MAX_AGE):
        return False
    death_year = parent.death.year if (parent.death and is_valid(parent.death)) else None
    return death_year is None or fixed <= death_year + 1


def suggest_century_typo(
    person: PersonFacts, family: FamilyFacts,
    parents: list[PersonFacts], siblings: list[PersonFacts],
) -> PropositionAudit | None:
    """D-coquille-de-siècle: birth impossible with the parents, but year-100 becomes
    plausible (parents alive, aged 15-60; coherent with dated siblings) — cas I2002. Pure."""
    if not is_valid(person.birth) or not person.birth.year:
        return None
    year = person.birth.year

    # Impossible aujourd'hui ? (parent mort avant, ou âge parental > 100 ans)
    impossible = False
    for parent in parents:
        if parent is None or not is_valid(parent.birth) or parent.birth.year is None:
            continue
        age = year - parent.birth.year
        death_year = parent.death.year if (parent.death and is_valid(parent.death)) else None
        if age > _CENTURY or (death_year is not None and year > death_year + 1):
            impossible = True
    if not impossible:
        return None

    # année-100 redevient-elle plausible pour TOUS les parents datés ?
    if not all(_century_fixed_ok(year, p) for p in parents):
        return None

    # cohérence avec la fratrie datée (fenêtre ±25 ans), si fratrie il y a
    sib_years = [s.birth.year for s in siblings
                 if s.handle != person.handle and is_valid(s.birth) and s.birth.year]
    if sib_years and not any(abs((year - _CENTURY) - y) <= _SIBLING_WINDOW
                             for y in sib_years):
        return None

    fixed = year - _CENTURY
    detail = (f"Naissance {year} impossible avec les parents de {family.gramps_id} ; "
              f"{fixed} redevient plausible"
              + (f" et cohérent avec la fratrie ({min(sib_years)}–{max(sib_years)})"
                 if sib_years else "") + ". Coquille d'un siècle probable.")
    return PropositionAudit(
        type="date", gramps_id=person.gramps_id, handle=person.handle,
        personne=person.name,
        cible=f"naissance de {person.gramps_id} ({year})",
        action=f"Corriger l'année de naissance de {person.name} : {year} → {fixed} "
               f"(coquille d'un siècle probable). Vérifier la citation rattachée avant "
               f"correction.",
        preuve_detail=detail, priorite="haute", confiance=1)
