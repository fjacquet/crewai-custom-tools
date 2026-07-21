"""Tests de la détection pure des doublons de lieux."""

import pytest

from crewai_custom_tools.tools.genealogy.analysis.place_duplicates import (
    PREUVE_CODE,
    PREUVE_COORDONNEES,
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


def test_meme_latitude_mais_longitude_differente_ne_prouve_pas():
    """La preuve porte sur le COUPLE, jamais sur la latitude seule.

    Deux communes entièrement géocodées peuvent partager une latitude au
    centième près sans partager la moindre position : le parallèle 47.11 traverse
    la France entière. Ne comparer que `lat` suffirait à faire fusionner
    automatiquement deux communes distinctes d'un même parallèle."""
    a = _lieu("P1", place_type="Municipality", lat="47.1147", long="2.0")
    b = _lieu("P2", place_type="Municipality", lat="47.1147", long="5.0")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


@pytest.mark.parametrize(
    ("type_a", "type_b"),
    [("Unknown", "Unknown"), ("", ""), ("", "Unknown"), ("Unknown", "Municipality")],
    ids=["deux-unknown", "deux-vides", "vide-contre-unknown", "unknown-contre-connu"],
)
def test_type_inconnu_ne_prouve_jamais_par_coordonnees(type_a, type_b):
    """L'ignorance n'est pas une valeur : un inconnu n'est égal à aucun autre.

    Scénario réel et programmé — le chantier référentiel va géocoder les
    contenants : un arrondissement « Bourges » encore sans type, géocodé au point
    de son chef-lieu, face à la commune « Bourges » sans type ni code. Même nom,
    aucun code pour opposer un veto, coordonnées identiques : si l'absence de
    type valait égalité de type, la fusion serait automatique et irréversible.

    Les deux orthographes de l'ignorance (`""` du modèle, `"Unknown"` de l'API)
    valent la même chose : le verdict ne doit pas dépendre de ce que rend l'API.
    """
    a = _lieu("P1", place_type=type_a, lat="47.0810", long="2.3988")
    b = _lieu("P2", place_type=type_b, lat="47.0810", long="2.3988")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_type_connu_reste_insensible_aux_blancs():
    """Le nettoyage des blancs ne doit pas casser la voie des coordonnées."""
    a = _lieu("P1", place_type=" Municipality ", lat=" 49.2708776 ", long=" 8.1234 ")
    b = _lieu("P2", place_type="Municipality", lat="49.2708776", long="8.1234")
    assert evaluer_preuve(a, b) == PREUVE_COORDONNEES
    assert evaluer_preuve(b, a) == PREUVE_COORDONNEES


@pytest.mark.parametrize(
    ("code_a", "code_b"),
    [(" ", " "), (" ", "  "), ("\t", " ")],
    ids=["memes-blancs", "blancs-de-longueurs-differentes", "tabulation-contre-espace"],
)
def test_codes_blancs_ne_prouvent_rien(code_a, code_b):
    """Un champ vidé en tapant une espace n'est pas un identifiant canonique.

    `" "` est truthy en Python ; sans nettoyage, deux codes blancs identiques se
    prouvent l'un l'autre — et le code prouve quel que soit le type, donc
    jusqu'entre un département et une commune."""
    a = _lieu("P0301", code=code_a, place_type="Department")
    b = _lieu("P0008", code=code_b, place_type="Municipality")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_code_blanc_ne_leve_pas_le_veto_ni_ne_prouve_face_a_un_vrai_code():
    """Un code blanc vaut un code absent : on retombe sur l'arbitrage humain."""
    a = _lieu("P1", code=" ", place_type="Municipality", lat="47.08", long="2.39")
    b = _lieu("P2", code="18033", place_type="Municipality", lat="47.08", long="2.39")
    assert evaluer_preuve(a, b) == PREUVE_COORDONNEES
    assert evaluer_preuve(b, a) == PREUVE_COORDONNEES


def test_coordonnees_blanches_ne_prouvent_rien():
    """Deux lieux « géocodés » à coups d'espaces ne partagent aucune position."""
    a = _lieu("P1", place_type="Municipality", lat=" ", long=" ")
    b = _lieu("P2", place_type="Municipality", lat="", long="")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


_PAIRES_SYMETRIE = [
    # (a, b) couvrant chaque branche du verdict, dans les deux sens.
    (_lieu("P1", code="18044", place_type="Municipality"),
     _lieu("P2", code="18044", place_type="City")),
    (_lieu("P1", code="75", place_type="Department", lat="48.8589", long="2.347"),
     _lieu("P2", code="75056", place_type="Municipality", lat="48.8589", long="2.347")),
    (_lieu("P1", place_type="Municipality", lat="49.27", long="8.12"),
     _lieu("P2", place_type="Municipality", lat="49.27", long="8.12")),
    (_lieu("P1", place_type="Department", lat="48.8589", long="2.347"),
     _lieu("P2", place_type="Municipality", lat="48.8589", long="2.347")),
    (_lieu("P1", place_type="Department"),
     _lieu("P2", place_type="Wilaya", code="23")),
    (_lieu("P1", place_type="Municipality", lat="47.1147"),
     _lieu("P2", place_type="Municipality", lat="47.1147", long="2.0")),
    (_lieu("P1", place_type="Municipality", lat="47.1147", long="2.0"),
     _lieu("P2", place_type="Municipality", lat="47.1147", long="5.0")),
    (_lieu("P1", place_type="Unknown", lat="47.08", long="2.39"),
     _lieu("P2", place_type="", lat="47.08", long="2.39")),
    # Coordonnées présentes à dessein : c'est la seule configuration où un côté
    # trancherait sur son propre code pendant que l'autre conclurait par la position.
    (_lieu("P1", code=" ", place_type="Municipality", lat="47.08", long="2.39"),
     _lieu("P2", code="18033", place_type="Municipality", lat="47.08", long="2.39")),
]


_IDS_SYMETRIE = [
    "codes-egaux", "codes-differents", "coordonnees-egales", "types-differents",
    "un-seul-code", "coordonnees-partielles", "longitudes-differentes",
    "types-inconnus", "code-blanc-contre-code",
]


@pytest.mark.parametrize(("a", "b"), _PAIRES_SYMETRIE, ids=_IDS_SYMETRIE)
def test_le_verdict_est_symetrique(a, b):
    """`evaluer_preuve` ne doit pas dépendre de l'ordre des deux lieux.

    L'appelant parcourt des paires non ordonnées ; une asymétrie ferait dépendre
    une fusion irréversible de l'ordre d'itération sur l'arbre — un lieu fusionné
    ou non selon la page d'API qui l'a rendu en premier."""
    assert evaluer_preuve(a, b) == evaluer_preuve(b, a)


def test_les_constantes_de_verdict_sont_les_valeurs_rendues():
    """Les deux verdicts sont exportés : l'appelant n'a pas à recopier de littéral."""
    assert (PREUVE_CODE, PREUVE_COORDONNEES) == ("code", "coordonnees")
