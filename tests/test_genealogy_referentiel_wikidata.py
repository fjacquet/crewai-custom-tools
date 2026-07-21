# tests/test_genealogy_referentiel_wikidata.py
"""Construction de requête et helpers purs du référentiel."""
from crewai_custom_tools.tools.genealogy.referentiel.wikidata import (
    build_query, build_query_pays, code_sans_prefixe, qid_of,
)


def test_qid_of_extrait_le_dernier_segment():
    assert qid_of("http://www.wikidata.org/entity/Q39") == "Q39"


def test_qid_of_laisse_passer_un_qid_nu():
    assert qid_of("Q39") == "Q39"


def test_qid_of_vide_sur_entree_vide():
    assert qid_of("") == ""
    assert qid_of(None) == ""


def test_code_sans_prefixe_reproduit_la_convention_de_larbre():
    # FR-03 -> 03, le code en base de l'Allier ; DZ-41 -> 41, celui de Souk Ahras.
    assert code_sans_prefixe("FR-03", "FR") == "03"
    assert code_sans_prefixe("DZ-41", "DZ") == "41"
    assert code_sans_prefixe("CH-VD", "CH") == "VD"


def test_code_sans_prefixe_rend_lentree_telle_quelle_si_le_prefixe_ne_colle_pas():
    assert code_sans_prefixe("IT-NA", "FR") == "IT-NA"


def test_build_query_filtre_le_prefixe_et_les_entites_dissoutes():
    q = build_query("CH", "de")
    assert 'STRSTARTS(?iso, "CH-")' in q
    assert "wdt:P576" in q            # dissolution : exclue
    assert "wdt:P300" in q            # ISO 3166-2 : le sélecteur
    assert "wdt:P625" in q            # coordonnées
    assert "wdt:P131" in q            # rattachement, d'où vient le niveau
    assert "fr.wikipedia.org" in q    # sitelink de l'article français


def test_build_query_demande_le_nom_vernaculaire():
    """Sans lui, `Bayern` déjà en base ne serait apparié par aucun nom au premier run,
    et un doublon `Bavière` serait créé à côté."""
    q = build_query("DE", "de")
    assert "rdfs:label" in q
    assert '"de"' in q


def test_build_query_pays_liste_les_qid_en_values():
    q = build_query_pays(["Q142", "Q39"])
    assert "wd:Q142" in q and "wd:Q39" in q
    assert "VALUES" in q
