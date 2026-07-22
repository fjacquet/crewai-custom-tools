from crewai_custom_tools.tools.genealogy.geo.score import (
    fuzzy_score,
    is_ambiguous,
    similarity,
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


def test_best_similarity_strips_paren_suffix():
    from crewai_custom_tools.tools.genealogy.geo.score import best_similarity
    assert best_similarity("Lausanne", "Lausanne (VD)") == 1.0
    assert best_similarity("Bern", "Bern (BE)") == 1.0

def test_best_similarity_multiscript_token():
    from crewai_custom_tools.tools.genealogy.geo.score import best_similarity
    assert best_similarity("Annaba", "Annaba ⵄⴻⵍⵃⴲⵃ عنابة") == 1.0

def test_best_similarity_monotone_ge_similarity():
    from crewai_custom_tools.tools.genealogy.geo.score import best_similarity, similarity
    for a, b in [("Lausanne", "Lausanne (VD)"), ("Aix en Provence", "Aix-en-Provence"),
                 ("Paris", "Marseille"), ("x", "y"),
                 ("", ""), ("", "   "), ("Paris", "")]:
        assert best_similarity(a, b) >= similarity(a, b)

def test_best_similarity_no_substring_inflation():
    from crewai_custom_tools.tools.genealogy.geo.score import best_similarity
    # a shorter query must not reach 1.0 against a longer token
    assert best_similarity("Ann", "Annaba") < 1.0
