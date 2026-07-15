"""
Grading utility for the A+ Investment Scoring cluster — composite score to
letter grade (A+ to F).

Port note: ported from finwiz's ``scoring/grading_system.py``. Only
``score_to_grade`` (plus its ``GradeInfo``/``Grade`` types) is ported here —
tracing usage shows it is the only piece the A+ grading cluster
(``APlusScoringTool``) calls. finwiz's ``format_grade_display`` and
``count_grade_distribution`` are report-formatting helpers used by finwiz's
portfolio reporting layer, not by this cluster, so per the porting brief
("port only what the cluster uses") they were left behind.
"""

from dataclasses import dataclass
from typing import Literal

# Type definitions for grades
Grade = Literal["A+", "A", "B+", "B", "C+", "C", "D", "F"]


@dataclass
class GradeInfo:
    """Information about a letter grade."""

    grade: Grade
    percentage: float
    description: str
    action: str
    emoji: str


def score_to_grade(composite_score: float) -> GradeInfo:
    """
    Convert composite score (0.0-1.0) to letter grade with actionable information.

    Args:
        composite_score: Float between 0.0 and 1.0

    Returns:
        GradeInfo object with grade, description, and recommended action

    """
    percentage = composite_score * 100

    if percentage >= 95:
        return GradeInfo(
            grade="A+",
            percentage=percentage,
            description="Excellent - Champion du portefeuille",
            action="Augmentez l'allocation si possible",
            emoji="🏆",
        )
    elif percentage >= 85:
        return GradeInfo(
            grade="A",
            percentage=percentage,
            description="Très bon - Investissement de qualité",
            action="Maintenez et continuez le DCA",
            emoji="⭐",
        )
    elif percentage >= 80:
        return GradeInfo(
            grade="B+",
            percentage=percentage,
            description="Bon+ - Solide avec potentiel",
            action="Conservez et surveillez les opportunités",
            emoji="📈",
        )
    elif percentage >= 75:
        return GradeInfo(
            grade="B",
            percentage=percentage,
            description="Bon - Satisfaisant à conserver",
            action="Maintenez, continuez le DCA",
            emoji="✅",
        )
    elif percentage >= 70:
        return GradeInfo(
            grade="C+",
            percentage=percentage,
            description="Passable+ - Acceptable avec surveillance",
            action="Conservez mais surveillez de près",
            emoji="⚠️",
        )
    elif percentage >= 65:
        return GradeInfo(
            grade="C",
            percentage=percentage,
            description="Passable - Minimum acceptable",
            action="Maintenez mais ne renforcez pas",
            emoji="🔍",
        )
    elif percentage >= 50:
        return GradeInfo(
            grade="D",
            percentage=percentage,
            description="Insuffisant - À améliorer rapidement",
            action="Réduisez progressivement la position",
            emoji="⚡",
        )
    else:
        return GradeInfo(
            grade="F",
            percentage=percentage,
            description="Échec - Élimination immédiate",
            action="Vendez immédiatement",
            emoji="❌",
        )
