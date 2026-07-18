"""Tests hors-ligne de l'inférence de genre et du modèle Proposition."""

from crewai_custom_tools.tools.genealogy.models.domain import Proposition


def test_proposition_roundtrip():
    p = Proposition(
        type="genre_inconnu", gramps_id="I0001", handle="h1", personne="Suzanne Martin",
        valeur_actuelle="U", valeur_proposee="F",
        preuve="prénom « SUZANNE » : 99.0% F sur 41230 (INSEE+OFS)",
        confiance="haute", priorite="moyenne",
    )
    assert p.champ == "gender"                      # défaut
    d = p.model_dump()
    assert Proposition(**d) == p                    # round-trip
