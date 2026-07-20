"""Construction/validation des modèles de domaine de l'audit."""

from crewai_custom_tools.tools.genealogy.models.domain import (
    Anomaly,
    DuplicateCandidate,
    EventFact,
    FamilyFacts,
    PersonFacts,
)


def test_eventfact_defaults():
    e = EventFact(type="Birth", sortval=2346578, year=1712)
    assert e.modifier == 0 and e.quality == 0 and e.has_citation is False


def test_personfacts_minimal_and_lists_default_empty():
    p = PersonFacts(gramps_id="I0001", handle="h1", name="Jean Test",
                    surname="Test", given="Jean", sex="M")
    assert p.birth is None and p.death is None
    assert p.events == [] and p.family_handles == [] and p.parent_family_handles == []
    assert p.has_any_citation is False


def test_familyfacts_and_anomaly_and_duplicate():
    f = FamilyFacts(gramps_id="F0001", handle="fh1")
    assert f.father_handle is None and f.child_handles == [] and f.marriage is None
    a = Anomaly(rule="R1", severity="haute", gramps_id="I0001", handle="h1",
                message="naissance après décès")
    assert a.detail == {}
    d = DuplicateCandidate(gramps_id_a="I0001", gramps_id_b="I0002",
                           score=0.91, reason="homonymes, naissances proches")
    assert d.score == 0.91


def test_piste_champs_et_defauts():
    from crewai_custom_tools.tools.genealogy.models.domain import Piste

    p = Piste(gramps_id="I1123", handle="h1", source="matchid",
              identite="a1b2c3d4", requete="nom=SOULAT&prenom=Kleber",
              concordances=["nom", "date complète"],
              divergences=[])
    assert p.identite_derivee is False       # défaut : identité native de la source
    assert p.url is None                     # défaut : aucune URL inventée
    assert p.force == "forte"                # dérivé : deux facteurs distincts, aucune divergence


def test_piste_concordance_hors_vocabulaire_refusee():
    import pytest
    from pydantic import ValidationError
    from crewai_custom_tools.tools.genealogy.models.domain import Piste

    # `concordances` est Literal, pas str libre : le contrat (vocabulaire fermé des
    # facteurs) est garanti par le modèle, pas par la discipline de chaque émetteur.
    # « né en 1888 » est précisément la formulation que la règle « année seule jamais
    # discriminante » interdit — elle doit être rejetée avant même d'atteindre la règle.
    with pytest.raises(ValidationError):
        Piste(gramps_id="I1", handle="h", source="s", identite="i",
              requete="q", concordances=["né en 1888"], divergences=[])


def test_piste_deux_facteurs_distincts_sans_divergence_est_forte():
    from crewai_custom_tools.tools.genealogy.models.domain import Piste

    p = Piste(gramps_id="I1", handle="h", source="s", identite="i", requete="q",
              concordances=["nom", "lieu"], divergences=[])
    assert p.force == "forte"


def test_piste_doublon_ne_compte_pas_pour_deux_facteurs():
    from crewai_custom_tools.tools.genealogy.models.domain import Piste

    p = Piste(gramps_id="I1", handle="h", source="s", identite="i", requete="q",
              concordances=["nom", "nom"], divergences=[])
    assert p.force == "faible"


def test_piste_divergence_degrade_malgre_deux_facteurs_valides():
    from crewai_custom_tools.tools.genealogy.models.domain import Piste

    p = Piste(gramps_id="I1", handle="h", source="s", identite="i", requete="q",
              concordances=["nom", "prénom"], divergences=["départements incompatibles"])
    assert p.force == "faible"


def test_piste_force_ne_peut_pas_etre_imposee_au_constructeur():
    from crewai_custom_tools.tools.genealogy.models.domain import Piste

    # `force` n'est plus un paramètre du constructeur : ce n'est plus un champ, c'est
    # un `computed_field`. pydantic ignore silencieusement le kwarg surnuméraire
    # (comportement par défaut, extra="ignore") — la valeur calculée gagne toujours.
    p = Piste(gramps_id="I1", handle="h", source="s", identite="i", requete="q",
              concordances=["nom"], divergences=[], force="forte")
    assert p.force == "faible"  # un seul facteur : la valeur imposée n'a pas pris
