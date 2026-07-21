"""GrampsMergePeopleTool — phoenix survit, titanic disparaît. Irréversible."""

import json

import pytest

from crewai_custom_tools.tools.genealogy.gramps import write_tools
from crewai_custom_tools.tools.genealogy.gramps.write_tools import GrampsMergePeopleTool


class _ClientEspion:
    def __init__(self):
        self.appels = []

    def request(self, methode, chemin, **kwargs):
        self.appels.append((methode, chemin, kwargs))
        return type("R", (), {"content": b"", "json": lambda self: {}})()


@pytest.fixture
def espion(monkeypatch):
    client = _ClientEspion()
    monkeypatch.setattr(write_tools, "get_client", lambda: client)
    # effective_dry_run() simule par défaut quand la variable est ABSENTE (voir
    # write_tools.effective_dry_run et le gotcha CLAUDE.md correspondant) : un simple
    # delenv laisserait donc les tests d'écriture réelle échouer même avec dry_run=False
    # explicite. On la force à "false" ici, comme le fait déjà
    # test_genealogy_place_merge_tool.py pour GrampsMergePlacesTool.
    monkeypatch.setenv("GENECREW_DRY_RUN", "false")
    return client


def test_dry_run_n_ecrit_rien(espion):
    payload = json.loads(GrampsMergePeopleTool()._run(
        phoenix_handle="hA", titanic_handle="hB", dry_run=True))
    assert payload["success"] is True
    assert payload["data"]["dry_run"] is True
    assert espion.appels == []


def test_ecriture_reelle_appelle_le_bon_endpoint(espion):
    payload = json.loads(GrampsMergePeopleTool()._run(
        phoenix_handle="hA", titanic_handle="hB", dry_run=False))
    assert payload["success"] is True
    methode, chemin, kwargs = espion.appels[0]
    assert methode == "POST"
    assert chemin == "/people/hA/merge/hB"
    assert kwargs["json"] == {"family_merger": True}


def test_family_merger_desactivable(espion):
    GrampsMergePeopleTool()._run(phoenix_handle="hA", titanic_handle="hB",
                                 family_merger=False, dry_run=False)
    assert espion.appels[0][2]["json"] == {"family_merger": False}


def test_env_force_la_simulation(espion, monkeypatch):
    """GENECREW_DRY_RUN ne peut que rendre l'appel PLUS sûr."""
    monkeypatch.setenv("GENECREW_DRY_RUN", "true")
    payload = json.loads(GrampsMergePeopleTool()._run(
        phoenix_handle="hA", titanic_handle="hB", dry_run=False))
    assert payload["data"]["dry_run"] is True
    assert espion.appels == []
