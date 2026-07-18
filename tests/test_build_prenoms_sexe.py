"""Test hors-ligne du build de la table prénoms (fixtures, sans réseau).

Tous les tests passent des chemins locaux (--insee / --ofs-*), donc les
téléchargements (download_insee / download_ofs) ne sont jamais appelés.
"""

import csv

from build_prenoms_sexe import build


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def _rows(out):
    return {r["prenom"]: (int(r["n_f"]), int(r["n_m"]))
            for r in csv.DictReader(open(out, encoding="utf-8"))}


def test_build_insee_only_aggregates_across_years(tmp_path):
    # Format INSEE 2025 : sexe;prenom;periode;valeur;rang — on agrège sur les années.
    insee = tmp_path / "nat.csv"
    _write(insee,
           "sexe;prenom;periode;valeur;rang\n"
           "1;JEAN;1900;100;1\n"
           "1;JEAN;1901;50;1\n"
           "2;MARIE;1900;200;1\n"
           "1;JOSÉ;1980;30;5\n")
    out = tmp_path / "prenoms_sexe.csv"
    build(insee=str(insee), out=out, with_ofs=False)   # INSEE seul, pas de réseau
    rows = _rows(out)
    assert rows["JEAN"] == (0, 150)           # 1900 + 1901 agrégés
    assert rows["MARIE"] == (200, 0)
    assert rows["JOSE"] == (0, 30)            # accent retiré via normkey


def test_build_merges_insee_and_ofs(tmp_path):
    # OFS : vrai format population (CSV ',', colonnes firstname / VALUE, un fichier par sexe).
    insee = tmp_path / "nat.csv"
    _write(insee, "sexe;prenom;periode;valeur;rang\n2;MARIE;1900;200;1\n1;JEAN;1900;150;1\n")
    ofs_f = tmp_path / "ofs_f.csv"
    _write(ofs_f,
           "TIME_PERIOD,firstname,YEAROFBIRTH,VALUE,OBS_STATUS\n"
           '"2024","Marie","1950","10","A"\n')
    ofs_m = tmp_path / "ofs_m.csv"
    _write(ofs_m,
           "TIME_PERIOD,firstname,YEAROFBIRTH,VALUE,OBS_STATUS\n"
           '"2024","Jean","1950","5","A"\n'
           '"2024","Ueli","1960","40","A"\n')
    out = tmp_path / "prenoms_sexe.csv"
    build(insee=str(insee), ofs_f=str(ofs_f), ofs_m=str(ofs_m), out=out)
    rows = _rows(out)
    assert rows["MARIE"] == (210, 0)          # INSEE 200 + OFS-f 10
    assert rows["JEAN"] == (0, 155)           # INSEE 150 + OFS-m 5
    assert rows["UELI"] == (0, 40)            # clé propre à l'OFS (suisse)


def test_build_tolerates_legacy_insee_header(tmp_path):
    # Ancienne édition INSEE : preusuel;annais;nombre — le parseur reste compatible.
    insee = tmp_path / "old.csv"
    _write(insee, "sexe;preusuel;annais;nombre\n2;SUZANNE;1930;500\n")
    out = tmp_path / "t.csv"
    build(insee=str(insee), out=out, with_ofs=False)
    assert _rows(out)["SUZANNE"] == (500, 0)
