"""Tests de la détection pure des doublons de lieux."""

from crewai_custom_tools.tools.genealogy.analysis.place_duplicates import (
    evaluer_preuve,
    normaliser_nom_lieu,
)
from crewai_custom_tools.tools.genealogy.models.domain import PlaceFacts


def test_casse_accents_et_separateurs_convergent():
    assert normaliser_nom_lieu("Saint-Palais") == normaliser_nom_lieu("SAINT PALAIS")
    assert normaliser_nom_lieu("Nohant-en-Goût") == normaliser_nom_lieu("nohant en gout")


def test_apostrophe_typographique_equivaut_a_l_ascii():
    """L'apostrophe courbe est l'usage typographique standard ; elle arrive par copier-coller."""
    assert normaliser_nom_lieu("L'Isle-Adam") == normaliser_nom_lieu("L’Isle-Adam")


def test_ligature_oe_equivaut_a_oe():
    """NFD décompose les accents, pas les ligatures. Vœuil-et-Giget (Charente) et
    Œuilly (Aisne) sont des communes réelles ; Ænes est un hameau norvégien réel —
    la ligature en minuscule (œ) et en majuscule (Œ, Æ) doit converger avec sa forme
    dépliée (« oe », « OE », « ae », « AE »)."""
    assert normaliser_nom_lieu("Vœuil-et-Giget") == normaliser_nom_lieu("Voeuil-et-Giget")
    assert normaliser_nom_lieu("Œuilly") == normaliser_nom_lieu("Oeuilly")
    assert normaliser_nom_lieu("Ænes") == normaliser_nom_lieu("Aenes")


def test_lettre_barree_ne_converge_pas_avec_sa_transliteration():
    """La table _LIGATURES couvre les ligatures (œ, æ), pas les lettres barrées.
    ø/Ø est une lettre scandinave à part entière, qu'Unicode ne décompose pas et
    qui n'est ni un accent ni une ligature composée. La transformer en "o" serait
    un choix arbitraire : rien ne justifierait alors d'ignorer le ł polonais ou le
    đ croate. Décision délibérée : les lettres barrées restent hors du périmètre
    de cette table, et Tønder ne doit pas s'y confondre avec Tonder."""
    assert normaliser_nom_lieu("Tønder") != normaliser_nom_lieu("Tonder")


def test_l_apostrophe_reste_un_separateur_et_ne_disparait_pas():
    """Si l'apostrophe était supprimée au lieu d'être séparée, deux communes
    distinctes se confondraient."""
    assert normaliser_nom_lieu("L'Isle-Adam") != normaliser_nom_lieu("Lisle-Adam")


def test_chaine_vide_et_blancs():
    assert normaliser_nom_lieu("") == ""
    assert normaliser_nom_lieu("   ") == ""


def _lieu(gid, **kw):
    base = {"gramps_id": gid, "handle": "H" + gid, "nom": "X"}
    base.update(kw)
    return PlaceFacts(**base)


def test_codes_identiques_prouvent_quel_que_soit_le_type():
    """Un code officiel est un identifiant canonique, pas une ressemblance."""
    a = _lieu("P1", code="18044", place_type="Municipality")
    b = _lieu("P2", code="18044", place_type="City")
    assert evaluer_preuve(a, b) == "code"


def test_codes_differents_opposent_un_veto():
    """Paris : Department 75 contre Municipality 75056 — deux entités réelles."""
    a = _lieu("P0301", code="75", place_type="Department", lat="48.8589", long="2.347")
    b = _lieu("P0008", code="75056", place_type="Municipality", lat="48.8589", long="2.347")
    assert evaluer_preuve(a, b) == ""


def test_coordonnees_identiques_prouvent_a_type_egal():
    """Rhodt unter Rietburg : deux Municipality sans code, mêmes coordonnées."""
    a = _lieu("P0119", place_type="Municipality", lat="49.2708776", long="8.1234")
    b = _lieu("P0103", place_type="Municipality", lat="49.2708776", long="8.1234")
    assert evaluer_preuve(a, b) == "coordonnees"


def test_coordonnees_ne_prouvent_rien_entre_types_differents():
    """Le chantier référentiel va géocoder les départements : ce refus doit tenir."""
    a = _lieu("P0301", place_type="Department", lat="48.8589", long="2.347")
    b = _lieu("P0008", place_type="Municipality", lat="48.8589", long="2.347")
    assert evaluer_preuve(a, b) == ""


def test_un_seul_code_renseigne_ne_prouve_pas():
    """Annaba : Department sans code contre Wilaya code 23 — arbitrage humain."""
    a = _lieu("P0343", place_type="Department")
    b = _lieu("P0383", place_type="Wilaya", code="23")
    assert evaluer_preuve(a, b) == ""


def test_sans_code_ni_coordonnees_aucune_preuve():
    a = _lieu("P1", place_type="Municipality")
    b = _lieu("P2", place_type="Municipality")
    assert evaluer_preuve(a, b) == ""


def test_coordonnees_partielles_ne_prouvent_pas():
    """Une latitude égale et une longitude vide n'est pas une coïncidence de position."""
    a = _lieu("P1", place_type="Municipality", lat="47.1147")
    b = _lieu("P2", place_type="Municipality", lat="47.1147", long="2.0")
    assert evaluer_preuve(a, b) == ""
