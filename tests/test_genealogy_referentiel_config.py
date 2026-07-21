# tests/test_genealogy_referentiel_config.py
"""La table des pays est une donnée dure : QID vérifiés, niveaux cohérents."""
from crewai_custom_tools.tools.genealogy.referentiel.config import PAYS_REFERENTIEL


def test_les_neuf_pays_attendus_sont_presents():
    assert set(PAYS_REFERENTIEL) == {"FR", "CH", "DE", "IT", "DZ", "US", "PL", "BE", "SY"}


def test_qid_des_pays_verifies_en_ligne_le_2026_07_21():
    attendus = {"FR": "Q142", "CH": "Q39", "DE": "Q183", "IT": "Q38", "DZ": "Q262",
                "US": "Q30", "PL": "Q36", "BE": "Q31", "SY": "Q858"}
    assert {c: p.qid for c, p in PAYS_REFERENTIEL.items()} == attendus


def test_niveaux_par_pays():
    # Deux niveaux là où l'arbre en a déjà deux ; un seul ailleurs (spec §4).
    assert PAYS_REFERENTIEL["FR"].niveaux == ("Region", "Department")
    assert PAYS_REFERENTIEL["IT"].niveaux == ("Region", "Province")
    assert PAYS_REFERENTIEL["BE"].niveaux == ("Region", "Province")
    assert PAYS_REFERENTIEL["CH"].niveaux == ("State",)
    assert PAYS_REFERENTIEL["DZ"].niveaux == ("Province",)


def test_langue_locale_par_pays():
    """Sert à récupérer le nom vernaculaire, seule prise pour apparier les 4 Länder
    déjà en base sous `Bayern`, `Hessen`… avant qu'aucun QID ne soit posé."""
    assert PAYS_REFERENTIEL["DE"].langue == "de"
    assert PAYS_REFERENTIEL["IT"].langue == "it"
    assert PAYS_REFERENTIEL["PL"].langue == "pl"
    assert PAYS_REFERENTIEL["US"].langue == "en"
    assert PAYS_REFERENTIEL["FR"].langue == "fr"


def test_aucun_type_personnalise():
    # Gramps ne connaît que ses types natifs ; Canton et Wilaya n'en font pas partie.
    natifs = {"Country", "State", "County", "City", "Province", "Region", "Department",
              "Municipality", "District", "Borough", "Town", "Village", "Locality"}
    for pays in PAYS_REFERENTIEL.values():
        assert set(pays.niveaux) <= natifs, pays.nom


def test_le_code_iso_de_la_cle_est_celui_du_pays():
    for code, pays in PAYS_REFERENTIEL.items():
        assert pays.code_iso == code
