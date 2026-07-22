"""Pure D-rule detectors — the crew v5 finds (I0010, I2002), now free. Offline."""

from crewai_custom_tools.tools.genealogy.analysis.corrections import (
    suggest_century_typo,
    suggest_misattached_parent_event,
)
from crewai_custom_tools.tools.genealogy.models.domain import (
    EventFact,
    FamilyFacts,
    PersonFacts,
)


def _event(kind, year, sortval):
    return EventFact(type=kind, year=year, sortval=sortval,
                     dateval=[1, 1, year, False])


def _person(gid, name, birth=None, death=None, events=()):
    return PersonFacts(gramps_id=gid, handle=f"h{gid}", name=name,
                       surname=name.split()[-1], given=name.split()[0], sex="U",
                       birth=birth, death=death, events=list(events))


# --- D-mariage-des-parents (cas I0010 Claude Villaudy) ---

def test_event_matching_parents_marriage_is_flagged():
    marriage = _event("Marriage", 1701, 2342000)
    claude = _person("I0010", "Claude Villaudy",
                     birth=_event("Birth", 1703, 2342800),
                     events=[_event("Marriage", 1701, 2342000)])   # même sortval
    fam = FamilyFacts(gramps_id="F0011", handle="hF", marriage=marriage)
    prop = suggest_misattached_parent_event(claude, [fam])
    assert prop is not None
    assert prop.type == "relation" and prop.confiance == 2
    assert "F0011" in prop.action and "1701" in prop.action
    assert prop.gramps_id == "I0010"


def test_pre_birth_event_with_different_year_is_not_flagged():
    claude = _person("I0010", "Claude Villaudy",
                     birth=_event("Birth", 1703, 2342800),
                     events=[_event("Marriage", 1700, 2341500)])   # autre ANNÉE
    fam = FamilyFacts(gramps_id="F0011", handle="hF",
                      marriage=_event("Marriage", 1701, 2342000))
    assert suggest_misattached_parent_event(claude, [fam]) is None


def test_same_year_different_precision_is_flagged_confiance_1():
    # cas réel I0010 : événement « 1701 » (année seule) vs mariage « 31/01/1701 »
    claude = _person("I0010", "Claude Villaudy",
                     birth=_event("Birth", 1703, 2343068),
                     events=[_event("Marriage", 1701, 2342338)])
    fam = FamilyFacts(gramps_id="F0011", handle="hF",
                      marriage=_event("Marriage", 1701, 2342368))
    prop = suggest_misattached_parent_event(claude, [fam])
    assert prop is not None and prop.confiance == 1
    assert "même année" in prop.action


def test_post_birth_marriage_is_normal():
    p = _person("I1", "A B", birth=_event("Birth", 1700, 2341000),
                events=[_event("Marriage", 1725, 2350000)])
    fam = FamilyFacts(gramps_id="F1", handle="hF",
                      marriage=_event("Marriage", 1725, 2350000))
    assert suggest_misattached_parent_event(p, [fam]) is None


# --- D-coquille-de-siècle (cas I2002 Jeanne Villaudy) ---

def _villaudy_family():
    father = _person("I9", "Pere Villaudy", birth=_event("Birth", 1675, 2332000),
                     death=_event("Death", 1738, 2355000))
    mother = _person("I8", "Jeanne Jamin", birth=_event("Birth", 1679, 2333500),
                     death=_event("Death", 1752, 2360000))
    sib = _person("I7", "Frere Villaudy", birth=_event("Birth", 1710, 2345300))
    fam = FamilyFacts(gramps_id="F0011", handle="hF")
    return father, mother, sib, fam


def test_century_typo_detected_when_minus_100_fits():
    father, mother, sib, fam = _villaudy_family()
    jeanne = _person("I2002", "Jeanne Villaudy", birth=_event("Birth", 1828, 2388400))
    prop = suggest_century_typo(jeanne, fam, [father, mother], [sib, jeanne])
    assert prop is not None
    assert prop.type == "date" and prop.priorite == "haute" and prop.confiance == 1
    assert "1828 → 1728" in prop.action
    assert "citation" in prop.action                           # vérifier la source d'abord


def test_no_typo_when_birth_is_compatible():
    father, mother, sib, fam = _villaudy_family()
    ok = _person("I3", "Ok Villaudy", birth=_event("Birth", 1712, 2346000))
    assert suggest_century_typo(ok, fam, [father, mother], [sib]) is None


def test_no_typo_when_minus_100_still_impossible():
    father, mother, sib, fam = _villaudy_family()
    # 1795-100=1695: la mère (née 1679) aurait 16 ans -> ok père 20... mais
    # utilisons un cas où -100 reste impossible: né 1890 -> 1790, parents morts 1738/1752
    p = _person("I4", "Trop Tard", birth=_event("Birth", 1890, 2411000))
    assert suggest_century_typo(p, fam, [father, mother], [sib]) is None


def test_no_typo_when_siblings_do_not_fit():
    father, mother, _, fam = _villaudy_family()
    # né 1770 -> 1670: parents pas encore en âge (père né 1675) -> refus via parents;
    # prenons 1802 -> 1702: parents ok (27/23) mais fratrie datée à 1698±25 -> 1702 ok...
    # cas de refus fratrie: né 1850 -> 1750: parents morts 1738/1752 -> mère limite,
    # père mort -> refus parents. Fratrie seule: né 1799 -> 1699 vs fratrie 1750
    sib_late = _person("I5", "Frere Tardif", birth=_event("Birth", 1750, 2359500))
    p = _person("I2", "Ecart Fratrie", birth=_event("Birth", 1799, 2377600))
    # parents: père né 1675 -> 1699-1675=24 ok; mère 1679 -> 20 ok; père mort 1738 ok
    assert suggest_century_typo(p, fam, [father, mother], [sib_late]) is None
