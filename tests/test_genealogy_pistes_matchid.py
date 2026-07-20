from crewai_custom_tools.tools.genealogy.models.domain import EventFact, PersonFacts
from crewai_custom_tools.tools.genealogy.pistes import event_iso, norm_nom, pistes_matchid


def _person(surname="DUPONT", given="Jean", birth_dateval=None):
    birth = EventFact(type="Birth", year=1900,
                      dateval=birth_dateval or [14, 7, 1900, False])
    return PersonFacts(gramps_id="I0042", handle="H42", name=f"{given} {surname}",
                       surname=surname, given=given, sex="M", birth=birth)


def test_norm_nom_retire_accents_et_majuscule():
    assert norm_nom("Mérigot") == "MERIGOT"


def test_event_iso_date_complete_fait_dix_caracteres():
    assert event_iso(EventFact(type="Birth", year=1900,
                               dateval=[14, 7, 1900, False])) == "1900-07-14"


def test_event_iso_annee_seule_fait_quatre_caracteres():
    assert event_iso(EventFact(type="Birth", year=1900, dateval=[0, 0, 1900, False])) == "1900"


def test_piste_forte_avec_nom_et_date_complete():
    match = {"id": "abc123", "name": {"last": "Dupont"},
             "birth": {"date": "19000714"}}
    piste = pistes_matchid(_person(), match, "https://deces.matchid.io/id/abc123")
    assert piste.source == "matchid" and piste.identite == "abc123"
    assert set(piste.concordances) == {"nom", "date complète"}
    assert piste.force == "forte"


def test_annee_seule_ne_donne_pas_de_second_facteur():
    # L'arbre ne connaît que l'année -> event_iso rend "1900" (4 car.), pas 10.
    person = _person(birth_dateval=[0, 0, 1900, False])
    match = {"id": "abc123", "name": {"last": "Dupont"}, "birth": {"date": "19000714"}}
    piste = pistes_matchid(person, match, "")
    assert piste.concordances == ["nom"]
    assert piste.force == "faible"


def test_dates_completes_differentes_donnent_une_divergence():
    match = {"id": "abc123", "name": {"last": "Dupont"}, "birth": {"date": "19010203"}}
    piste = pistes_matchid(_person(), match, "")
    assert piste.divergences == ["dates de naissance différentes"]
    assert piste.force == "faible"
