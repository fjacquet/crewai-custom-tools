from crewai_custom_tools.tools.genealogy.geo.score import (
    fuzzy_score, is_ambiguous, similarity,
)


def test_similarity_accent_and_case_insensitive():
    assert similarity("Zürich", "ZURICH") > 0.99


def test_fuzzy_score_penalizes_wrong_name():
    good = fuzzy_score(0.9, "Bourges", "Bourges")
    bad = fuzzy_score(0.9, "Bourges", "Paris")
    assert good > bad
    assert 0.0 <= bad <= good <= 1.0


def test_ambiguity_margin():
    assert is_ambiguous([0.95, 0.90]) is True      # marge 0.05 < 0.10
    assert is_ambiguous([0.95, 0.70]) is False     # marge 0.25 ≥ 0.10
    assert is_ambiguous([0.95]) is False           # un seul candidat
