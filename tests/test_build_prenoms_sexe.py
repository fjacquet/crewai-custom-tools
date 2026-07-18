"""Test hors-ligne du build de la table prénoms (fixtures)."""

import csv

from build_prenoms_sexe import build


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_build_merges_insee_and_ofs(tmp_path):
    insee = tmp_path / "nat.csv"
    _write(insee,
           "sexe;preusuel;annais;nombre\n"
           "1;JEAN;1900;100\n"
           "1;JEAN;1901;50\n"
           "2;MARIE;1900;200\n"
           "2;_PRENOMS_RARES;1900;9999\n"
           "1;JOSÉ;1980;30\n")
    ofs_f = tmp_path / "ofs_f.csv"
    _write(ofs_f, "prenom;nombre\nMarie;10\n")
    ofs_m = tmp_path / "ofs_m.csv"
    _write(ofs_m, "prenom;nombre\nJean;5\nUeli;40\n")
    out = tmp_path / "prenoms_sexe.csv"

    build(str(insee), str(ofs_f), str(ofs_m), str(out))

    rows = {r["prenom"]: (int(r["n_f"]), int(r["n_m"]))
            for r in csv.DictReader(open(out, encoding="utf-8"))}
    assert rows["JEAN"] == (0, 155)         # INSEE 150 + OFS-m 5
    assert rows["MARIE"] == (210, 0)        # INSEE 200 + OFS-f 10
    assert rows["JOSE"] == (0, 30)          # accent retiré
    assert rows["UELI"] == (0, 40)
    assert "_PRENOMS_RARES" not in rows     # exclu
