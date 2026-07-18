"""Tests hors-ligne de l'inférence de genre et du modèle Proposition."""

import csv

import pytest

from crewai_custom_tools.tools.genealogy.analysis.gender import (
    GenderInference, infer_sex, load_prenoms_table, normkey,
)
from crewai_custom_tools.tools.genealogy.models.domain import Proposition


def test_proposition_roundtrip():
    p = Proposition(
        type="genre_inconnu", gramps_id="I0001", handle="h1", personne="Suzanne Martin",
        valeur_actuelle="U", valeur_proposee="F",
        preuve="prénom « SUZANNE » : 99.0% F sur 41230 (INSEE+OFS)",
        confiance="haute", priorite="moyenne",
    )
    assert p.champ == "gender"                      # défaut
    d = p.model_dump()
    assert Proposition(**d) == p                    # round-trip


TABLE = {
    "PIERRE": (2, 9998),        # M net
    "SUZANNE": (9990, 10),      # F net
    "DOMINIQUE": (5000, 5000),  # unisexe
    "CAMILLE": (8000, 2000),    # 80% -> sous le seuil
    "RARE": (30, 1),            # volume < 50
    "JEAN-PIERRE": (1, 3000),   # composé présent
    "MARIE": (9990, 10),        # segment de repli
    "JEAN": (5, 9000),          # 1er prénom d'un given multiple
}


@pytest.mark.parametrize("raw, expected", [
    ("josé", "JOSE"),
    ("Jean-Marie", "JEAN-MARIE"),
    ("D’Abbadie", "D'ABBADIE"),    # apostrophe typographique U+2019
    ("OʼBrien", "O'BRIEN"),        # apostrophe modificative U+02BC
    ("saint‑affrique", "SAINT-AFFRIQUE"),  # trait insécable U+2011
    ("  Anne  ", "ANNE"),
])
def test_normkey(raw, expected):
    assert normkey(raw) == expected


@pytest.mark.parametrize("given, sex", [
    ("Pierre", "M"),
    ("Suzanne", "F"),
    ("Dominique", None),        # unisexe -> abstention
    ("Camille", None),          # 80% < 95% -> abstention
    ("Rare", None),             # volume 31 < 50 -> abstention
    ("Jean-Pierre", "M"),       # composé présent
    ("Marie-Antoinette", "F"),  # composé absent -> repli sur MARIE
    ("Jean Baptiste", "M"),     # 1er prénom d'un given multiple
    ("", None),                 # vide
    ("Zzznotfound", None),      # non couvert
])
def test_infer_sex(given, sex):
    assert infer_sex(given, TABLE).sex == sex


@pytest.mark.parametrize("n_f, n_m, expect_sex", [
    (48, 2, "F"),      # total=50, ratio=0.96 -> pile au seuil MIN_TOTAL, au-dessus du ratio -> propose
    (49, 0, None),     # total=49 (ratio 1.0) -> sous MIN_TOTAL=50 -> abstention
    (95, 5, "F"),      # total=100, ratio=0.95 pile -> propose (>=)
    (94, 6, None),     # total=100, ratio=0.94 -> sous MIN_RATIO=0.95 -> abstention
])
def test_infer_sex_thresholds(n_f, n_m, expect_sex):
    table = {"SEUIL": (n_f, n_m)}
    result = infer_sex("Seuil", table)
    if expect_sex is None:
        assert result.sex is None
    else:
        assert result.sex == expect_sex


def test_infer_sex_details():
    inf = infer_sex("Suzanne", TABLE)
    assert isinstance(inf, GenderInference)
    assert inf.total == 10000 and inf.key == "SUZANNE" and inf.ratio > 0.99
    assert infer_sex("Zzz", TABLE) == GenderInference(sex=None, ratio=0.0, total=0, key="")


def test_load_prenoms_table(tmp_path):
    csv_path = tmp_path / "t.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["prenom", "n_f", "n_m"])
        w.writerow(["SUZANNE", "9990", "10"])
    table = load_prenoms_table(csv_path)
    assert table["SUZANNE"] == (9990, 10)
