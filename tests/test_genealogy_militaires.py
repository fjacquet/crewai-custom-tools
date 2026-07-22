"""Offline tests: shared identity scoring + military gazetteer SQLite matching."""

import sqlite3

import pytest

from crewai_custom_tools.tools.genealogy.analysis.identity import (
    birth_concordance,
    score_identity,
)
from crewai_custom_tools.tools.genealogy.militaires import (
    match_militaires,
    query_militaires,
)

# --- scoring partagé ---

def test_birth_concordance_levels():
    assert birth_concordance("1895-11-11", "1895-11-11") == 1.0
    assert birth_concordance("1895-01-01", "1895-11-11") == 0.5   # même année
    assert birth_concordance("1895", "1895-11-11") == 0.5
    assert birth_concordance("1896", "1895-11-11") == 0.0
    assert birth_concordance("", "1895-11-11") == 0.0


def test_score_identity_full_and_capped_year():
    s_full = score_identity("Villaudy", "Sylvain", "1895-11-11",
                            "VILLAUDY", ["Sylvain"], "1895-11-11")
    assert s_full == 1.0
    s_year = score_identity("Villaudy", "Sylvain", "1895",
                            "VILLAUDY", ["Sylvain"], "1895-11-11")
    assert s_year == 0.85                          # année seule: sous le seuil 0.90


# --- gazetteer sqlite ---

@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "militaires.sqlite"
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE deces_militaires (
        base TEXT, nom TEXT, nom_normalise TEXT, prenom TEXT,
        naissance_date TEXT, naissance_lieu TEXT, naissance_departement TEXT,
        naissance_pays TEXT, deces_date TEXT, deces_lieu TEXT, deces_pays TEXT,
        unite TEXT, reference TEXT, lien_ark TEXT, source_fichier TEXT)""")
    con.executemany(
        "INSERT INTO deces_militaires VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [("Guerre 1914-1918", "VILLAUDY", "villaudy", "Sylvain", "1895-11-11",
          "Paris 20e", "Seine", "France", "1915-09-28", "Neuville-Saint-Vaast", "France",
          "156e RI", "cl.1915", "https://ark/xyz", "f"),
         ("Guerre 1914-1918", "VILLAUDY", "villaudy", "Alexis", "1870-09-27",
          "", "", "France", "1917-05-02", "", "France", "", "", "", "f")])
    con.commit()
    con.close()
    return path


def test_query_by_normalized_surname(db):
    rows = query_militaires("Villaudy", db=db)                 # accents/casse gérés
    assert len(rows) == 2
    assert rows[0]["nom"] == "VILLAUDY"


def test_match_scores_and_orders(db):
    scored = match_militaires("Villaudy", "Sylvain", "1895-11-11", db=db)
    assert scored[0][0]["prenom"] == "Sylvain" and scored[0][1] == 1.0
    # Alexis: année divergente -> éliminé
    assert all(r["prenom"] != "Alexis" for r, _ in scored)


def test_query_returns_all_rows_for_common_surnames(tmp_path):
    # régression Léon Clavier: LIMIT 50 arbitraire perdait la bonne ligne (200 homonymes)
    import sqlite3 as _sq
    path = tmp_path / "big.sqlite"
    con = _sq.connect(path)
    con.execute("""CREATE TABLE deces_militaires (
        base TEXT, nom TEXT, nom_normalise TEXT, prenom TEXT,
        naissance_date TEXT, naissance_lieu TEXT, naissance_departement TEXT,
        naissance_pays TEXT, deces_date TEXT, deces_lieu TEXT, deces_pays TEXT,
        unite TEXT, reference TEXT, lien_ark TEXT, source_fichier TEXT)""")
    rows = [("b", "CLAVIER", "clavier", f"Louis {i}", "1889-01-01", "", "", "",
             "1915-01-01", "", "", "", "", "", "f") for i in range(199)]
    rows.append(("b", "CLAVIER", "clavier", "Léon", "1891-08-31", "St-Martin", "", "",
                 "1914-10-01", "", "", "", "", "https://ark/leon", "f"))
    con.executemany("INSERT INTO deces_militaires VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    scored = match_militaires("Clavier", "Léon", "1891-08-31", db=path)
    assert scored and scored[0][0]["prenom"] == "Léon" and scored[0][1] == 1.0


def test_missing_db_raises_explicit_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        query_militaires("X", db=tmp_path / "absent.sqlite")
