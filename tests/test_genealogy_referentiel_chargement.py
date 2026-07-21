# tests/test_genealogy_referentiel_chargement.py
"""Transport : reprises, pays en échec isolé, temporisation."""
from crewai_custom_tools.tools.genealogy.referentiel import chargement
from crewai_custom_tools.tools.genealogy.referentiel.config import PAYS_REFERENTIEL

CH = PAYS_REFERENTIEL["CH"]
ENTITE = "http://www.wikidata.org/entity/"


def test_charger_pays_rend_les_subdivisions(monkeypatch):
    # `ancre` porte l'atteinte du pays par P131 (voir wikidata.py) : sans elle, l'entité
    # dont l'unique parent EST le pays n'est rattachée à aucune ligne de l'univers et
    # `map_subdivisions` l'écarte comme « rattachement introuvable » (vérifié par essai).
    monkeypatch.setattr(chargement, "sparql_rows", lambda q, timeout=0: [
        {"item": ENTITE + "Q1273", "itemLabel": "Vaud", "iso": "CH-VD",
         "parent": ENTITE + "Q39", "ancre": "true"}])
    res = chargement.charger_pays(CH)
    assert res.erreur is None
    assert [s.iso for s in res.subdivisions] == ["CH-VD"]


def test_charger_pays_reessaye_puis_reussit(monkeypatch):
    appels = {"n": 0}

    def flaky(query, timeout=0):
        appels["n"] += 1
        if appels["n"] < 3:
            raise chargement.RequestException("502 Bad Gateway")
        return [{"item": ENTITE + "Q1273", "itemLabel": "Vaud", "iso": "CH-VD",
                 "parent": ENTITE + "Q39", "ancre": "true"}]

    monkeypatch.setattr(chargement, "sparql_rows", flaky)
    monkeypatch.setattr(chargement.time, "sleep", lambda s: None)
    res = chargement.charger_pays(CH, essais=3, pause=0.0)
    assert appels["n"] == 3
    assert res.erreur is None and len(res.subdivisions) == 1


def test_un_pays_en_echec_est_signale_et_ne_leve_pas(monkeypatch):
    def toujours_ko(query, timeout=0):
        raise chargement.RequestException("504 Gateway Timeout")

    monkeypatch.setattr(chargement, "sparql_rows", toujours_ko)
    monkeypatch.setattr(chargement.time, "sleep", lambda s: None)
    res = chargement.charger_pays(CH, essais=2, pause=0.0)
    assert res.subdivisions == [] and res.collisions == []
    assert "504" in res.erreur


def test_temporisation_avant_chaque_appel(monkeypatch):
    acquis = []
    monkeypatch.setattr(chargement, "sparql_rows", lambda q, timeout=0: [])
    monkeypatch.setattr(chargement, "get_rate_limiter",
                        lambda: type("L", (), {"acquire": lambda self, p: acquis.append(p)})())
    chargement.charger_pays(CH)
    assert acquis == ["Wikidata"]


def test_charger_entites_pays(monkeypatch):
    monkeypatch.setattr(chargement, "sparql_rows", lambda q, timeout=0: [
        {"item": ENTITE + "Q39", "itemLabel": "Suisse", "coord": "Point(8.23 46.80)",
         "art": "https://fr.wikipedia.org/wiki/Suisse"}])
    entites = chargement.charger_entites_pays(["Q39"])
    assert entites["Q39"].libelle_fr == "Suisse"
    assert (entites["Q39"].lat, entites["Q39"].long) == ("46.80", "8.23")
    assert entites["Q39"].frwiki.endswith("/Suisse")


def test_charger_entites_pays_en_echec_rend_un_dictionnaire_vide(monkeypatch):
    def ko(query, timeout=0):
        raise chargement.RequestException("boom")

    monkeypatch.setattr(chargement, "sparql_rows", ko)
    monkeypatch.setattr(chargement.time, "sleep", lambda s: None)
    assert chargement.charger_entites_pays(["Q39"], essais=1, pause=0.0) == {}
