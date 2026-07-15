"""Tests for the A+ grading cluster's score_to_grade utility.

Pure computation, no network — direct input/output assertions.
"""

import pytest

from crewai_custom_tools.tools.analytics.grading import GradeInfo, score_to_grade


@pytest.mark.parametrize(
    "score,expected_grade",
    [
        (1.00, "A+"),
        (0.95, "A+"),
        (0.90, "A"),
        (0.85, "A"),
        (0.82, "B+"),
        (0.80, "B+"),
        (0.77, "B"),
        (0.75, "B"),
        (0.72, "C+"),
        (0.70, "C+"),
        (0.67, "C"),
        (0.65, "C"),
        (0.55, "D"),
        (0.50, "D"),
        (0.30, "F"),
        (0.0, "F"),
    ],
)
def test_score_to_grade_boundaries(score, expected_grade):
    grade_info = score_to_grade(score)
    assert isinstance(grade_info, GradeInfo)
    assert grade_info.grade == expected_grade
    assert grade_info.percentage == pytest.approx(score * 100)


def test_score_to_grade_includes_french_description_action_and_emoji():
    grade_info = score_to_grade(0.97)
    assert grade_info.grade == "A+"
    assert "Champion" in grade_info.description
    assert grade_info.action
    assert grade_info.emoji == "🏆"
