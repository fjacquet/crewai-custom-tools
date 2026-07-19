"""Pure deterministic scoring of MatchID death matches (no network)."""

from crewai_custom_tools.tools.genealogy.matchid import (
    best_deces_match,
    score_deces_match,
)

ODETTE = {
    "name": {"first": ["Odette", "Henriette"], "last": "Rippert"},
    "sex": "F",
    "birth": {"date": "19220929",
              "location": {"city": "Departement De Constantine", "country": "Algerie"}},
    "death": {"date": "20211219", "age": 99, "location": {"city": "Bourges"}},
}


def test_exact_full_date_scores_one():
    s = score_deces_match("Rippert", "Odette", "1922-09-29", ODETTE)
    assert s == 1.0                                            # 0.5 + 0.2 + 0.3


def test_year_only_caps_below_proposal_threshold():
    # L'année seule plafonne à 0.85 : elle ne peut JAMAIS franchir le seuil 0.90 seule
    # (retour terrain: des vivants proposés décédés sur homonymes même-nom-même-année).
    s = score_deces_match("Rippert", "Odette", "1922", ODETTE)
    assert s == 0.85                                           # 0.5 + 0.2 + 0.15


def test_divergent_birth_eliminates():
    assert score_deces_match("Rippert", "Odette", "1931-01-01", ODETTE) == 0.0


def test_fuzzy_surname_lowers_score():
    s = score_deces_match("Ripert", "Odette", "1922-09-29", ODETTE)   # 1 lettre
    assert 0.85 < s < 1.0


def test_given_matches_any_first_name():
    s = score_deces_match("Rippert", "Henriette", "1922-09-29", ODETTE)
    assert s == 1.0                                            # 2e prénom INSEE


def test_best_match_picks_highest_and_drops_eliminated():
    other = {"name": {"first": ["Odile"], "last": "Ripper"},
             "birth": {"date": "19220310"}, "death": {"date": "19990101"}}
    wrong_year = {"name": {"first": ["Odette"], "last": "Rippert"},
                  "birth": {"date": "19310929"}}
    best = best_deces_match("Rippert", "Odette", "1922-09-29",
                            [wrong_year, other, ODETTE])
    assert best is not None
    match, score = best
    assert match is ODETTE and score == 1.0


def test_best_match_none_when_all_eliminated():
    assert best_deces_match("Rippert", "Odette", "1900",
                            [{"name": {"first": ["O"], "last": "R"},
                              "birth": {"date": "19220929"}}]) is None
