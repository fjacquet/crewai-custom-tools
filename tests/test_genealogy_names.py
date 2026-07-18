"""Tests par table des fonctions pures de normalisation de casse."""

import pytest

from crewai_custom_tools.tools.genealogy.standardize.names import (
    is_case_only_change,
    is_incomplete_name,
    needs_normalization,
    normalize_case,
)


@pytest.mark.parametrize("raw, expected", [
    ("JACQUET", "Jacquet"),
    ("BERNARD DE SAINT-AFFRIQUE", "Bernard de Saint-Affrique"),
    ("D'ABBADIE D'ARRAST", "d'Abbadie d'Arrast"),
    ("SAINT-AFFRIQUE", "Saint-Affrique"),
    ("MACDONALD", "MacDonald"),
    ("O'BRIEN", "O'Brien"),
    ("DE LA TOUR", "de la Tour"),
    ("", ""),
])
def test_normalize_case(raw, expected):
    assert normalize_case(raw) == expected


@pytest.mark.parametrize("name, expected", [
    ("JACQUET", True),      # tout capitales
    ("jacquet", True),      # tout minuscules
    ("Jacquet", False),     # déjà casse mixte
    ("van Beethoven", False),
    ("", False),
    ("18", False),          # pas de lettre
])
def test_needs_normalization(name, expected):
    assert needs_normalization(name) is expected


def test_is_case_only_change():
    assert is_case_only_change("JACQUET", "Jacquet") is True
    assert is_case_only_change("JACQUET", "Jacque") is False   # lettre perdue
    assert is_case_only_change("A  B", "A B") is False         # espace changé


@pytest.mark.parametrize("name, expected", [
    ("?, Suzanne", True),
    ("Louis 3", True),
    ("Jacquet", False),
])
def test_is_incomplete_name(name, expected):
    assert is_incomplete_name(name) is expected
