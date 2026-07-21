"""Contrats des modèles de fusion."""

import pytest
from pydantic import ValidationError

from crewai_custom_tools.tools.genealogy.models.domain import MergeCluster, MergePair


def test_paire_minimale():
    p = MergePair(gramps_id_a="I1", gramps_id_b="I2", handle_a="h1", handle_b="h2",
                  tier="auto", regle="date_complete+parents")
    assert p.tier == "auto"
    assert p.blocs == []


def test_tier_est_un_vocabulaire_ferme():
    with pytest.raises(ValidationError):
        MergePair(gramps_id_a="I1", gramps_id_b="I2", handle_a="h1", handle_b="h2",
                  tier="peut-etre", regle="")


def test_grappe_sans_patch_de_genre_par_defaut():
    g = MergeCluster(phoenix_handle="h1", phoenix_gramps_id="I1",
                     titanic_handles=["h2"], titanic_gramps_ids=["I2"])
    assert g.gender_patch is None


def test_grappe_refuse_un_genre_hors_vocabulaire():
    with pytest.raises(ValidationError):
        MergeCluster(phoenix_handle="h1", phoenix_gramps_id="I1",
                     titanic_handles=["h2"], titanic_gramps_ids=["I2"], gender_patch=7)


def test_place_facts_defauts_vides():
    """Un lieu sans code ni coordonnées se construit : l'arbre en est plein."""
    from crewai_custom_tools.tools.genealogy.models.domain import PlaceFacts

    p = PlaceFacts(gramps_id="P0068", handle="H68", nom="Saint-Palais")
    assert p.place_type == ""
    assert p.code == ""
    assert p.lat == "" and p.long == ""
    assert p.a_parent is False
    assert p.retroliens == 0


def test_place_facts_complet():
    from crewai_custom_tools.tools.genealogy.models.domain import PlaceFacts

    p = PlaceFacts(gramps_id="P0000", handle="H0", nom="Bourges",
                   place_type="Municipality", code="18033",
                   lat="47.0810", long="2.3988", a_parent=True, retroliens=53)
    assert (p.code, p.retroliens, p.a_parent) == ("18033", 53, True)


def test_place_merge_proposition_champs_de_rapport_optionnels():
    """Un YAML de fusions antérieur reste chargeable : les deux champs sont optionnels."""
    from crewai_custom_tools.tools.genealogy.models.domain import PlaceMergeProposition

    p = PlaceMergeProposition(
        gramps_id_keep="P0002", handle_keep="HA", gramps_id_merge="P0188",
        handle_merge="HB", canonical="Saint-Martin-d'Auxigny", reason="doublon")
    assert p.verdict == ""
    assert p.perte_evitee == ""
