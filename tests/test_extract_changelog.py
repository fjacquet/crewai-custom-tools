"""Tests de `scripts/extract_changelog.py` — découpage de CHANGELOG.md.

Le fichier fixture reproduit les trois formes réelles du CHANGELOG du dépôt :
une section avec descriptif dans le heading, une section sans descriptif et
sans séparateur `---` de fin (le cas de 0.21.1, 0.19.1, 0.2.0 et 0.1.0), et
une dernière section bornée par la fin du fichier.
"""

import pytest
from extract_changelog import RACINE, extraire, main, normaliser_version

CHANGELOG = """\
# Changelog

Prose d'introduction.

---

## [0.28.0] - 2026-07-22 — Fusion des lieux

### Added

- Le détecteur de doublons.

---

## [0.27.0] - 2026-07-22

### Changed

- Configuration de ruff.

## [0.26.0] - 2026-07-21

### Added

- Champs structurés.
"""


def test_titre_reprend_le_descriptif_du_heading():
    titre, _ = extraire(CHANGELOG, "0.28.0")
    assert titre == "v0.28.0 — Fusion des lieux"


def test_titre_retombe_sur_le_tag_sans_descriptif():
    titre, _ = extraire(CHANGELOG, "0.27.0")
    assert titre == "v0.27.0"


def test_corps_borne_par_la_section_suivante_et_separateur_retire():
    _, corps = extraire(CHANGELOG, "0.28.0")
    assert corps == "### Added\n\n- Le détecteur de doublons."


def test_corps_borne_sans_separateur_de_fin():
    _, corps = extraire(CHANGELOG, "0.27.0")
    assert corps == "### Changed\n\n- Configuration de ruff."


def test_derniere_section_bornee_par_la_fin_du_fichier():
    _, corps = extraire(CHANGELOG, "0.26.0")
    assert corps == "### Added\n\n- Champs structurés."


def test_version_absente_leve_key_error():
    with pytest.raises(KeyError):
        extraire(CHANGELOG, "9.9.9")


def test_tag_et_version_nue_designent_la_meme_section():
    assert normaliser_version("v0.28.0") == "0.28.0"
    assert normaliser_version("0.28.0") == "0.28.0"


def test_main_imprime_le_corps(tmp_path, capsys):
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(CHANGELOG, encoding="utf-8")
    code = main(["v0.28.0", "--fichier", str(fichier)])
    assert code == 0
    assert capsys.readouterr().out.strip() == "### Added\n\n- Le détecteur de doublons."


def test_main_imprime_le_titre(tmp_path, capsys):
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(CHANGELOG, encoding="utf-8")
    code = main(["v0.28.0", "--titre", "--fichier", str(fichier)])
    assert code == 0
    assert capsys.readouterr().out.strip() == "v0.28.0 — Fusion des lieux"


def test_main_echoue_bruyamment_si_la_version_est_absente(tmp_path, capsys):
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(CHANGELOG, encoding="utf-8")
    code = main(["v9.9.9", "--fichier", str(fichier)])
    assert code == 1
    capture = capsys.readouterr()  # une seule lecture : elle vide le tampon
    assert "9.9.9" in capture.err
    assert capture.out == ""


def test_main_echoue_sur_une_section_vide(tmp_path, capsys):
    """Un heading ajouté mais pas encore rempli ne doit pas publier de page blanche."""
    fichier = tmp_path / "CHANGELOG.md"
    fichier.write_text(
        "## [0.28.0] - 2026-07-23 — Section vide\n\n## [0.27.0] - 2026-07-22\n\n- Rempli.\n",
        encoding="utf-8",
    )
    code = main(["v0.28.0", "--fichier", str(fichier)])
    assert code == 1
    capture = capsys.readouterr()
    assert "vide" in capture.err
    assert capture.out == ""


def test_main_echoue_si_le_fichier_est_illisible(tmp_path, capsys):
    code = main(["v0.28.0", "--fichier", str(tmp_path / "absent.md")])
    assert code == 1
    capture = capsys.readouterr()
    assert "illisible" in capture.err
    assert capture.out == ""


def test_le_changelog_reel_expose_la_version_courante():
    """Garde de non-régression : le vrai CHANGELOG reste lisible par le script.

    Elle attrape en CI, avant même que le tag soit posé, les deux pannes qui
    feraient rougir le workflow de release : une entrée CHANGELOG oubliée pour
    la version courante, ou un heading dont la forme a dérivé.
    """
    from crewai_custom_tools import __version__

    texte = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
    titre, corps = extraire(texte, __version__)
    assert titre.startswith(f"v{__version__}")
    assert corps.strip()
