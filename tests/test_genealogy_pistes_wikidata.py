from crewai_custom_tools.tools.genealogy.models.domain import EventFact, PersonFacts
from crewai_custom_tools.tools.genealogy.pistes import pistes_wikidata, requete_wikidata


def _person(surname="Dupont", given="Jean", dateval=None, place_name="Montbéliard"):
    birth = EventFact(type="Birth", year=1677, dateval=dateval or [15, 7, 1677, False],
                      place_name=place_name,
                      place=f"{place_name}, Doubs, France" if place_name else "")
    return PersonFacts(gramps_id="I1234", handle="H1", name=f"{given} {surname}",
                       surname=surname, given=given, sex="M", birth=birth)


def test_requete_passe_par_le_service_indexe_pas_par_un_filtre():
    # Un FILTER(CONTAINS(...)) sur rdfs:label balaie les ~10 M d'humains de
    # Wikidata et rend 504 après 65 s — mesuré. La recherche DOIT être indexée.
    q = requete_wikidata(_person())
    assert "Dupont" in q and "SELECT" in q.upper()
    assert "EntitySearch" in q and "wikibase:mwapi" in q
    assert "CONTAINS" not in q.upper()


def test_roy_ne_correspond_pas_a_leroy():
    """Le faux positif qui motive la comparaison par mots entiers."""
    person = _person(surname="Roy", given="Silvain")
    rows = [{"item": "http://www.wikidata.org/entity/Q99", "itemLabel": "Silvain Leroy",
             "birthDate": "1677-07-15T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    assert "nom" not in pistes_wikidata(person, rows)[0].concordances


def test_prenom_en_liste_a_virgules_correspond_au_prenom_d_usage():
    # 20 % de l'arbre : 'Marcel, Hubert, Andre' = trois prénoms, pas un composé.
    person = _person(surname="Soulat", given="Marcel, Hubert, Andre")
    rows = [{"item": "http://www.wikidata.org/entity/Q99", "itemLabel": "Marcel Soulat",
             "birthDate": "1677-07-15T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    assert "nom" in pistes_wikidata(person, rows)[0].concordances


def test_trait_d_union_eclate_correspond_a_la_forme_espacee():
    # Cas réel vérifié : la recherche 'Guillaume-Henri Dufour' rend le libellé
    # Wikidata 'Guillaume Henri Dufour'. Sans éclatement, vrai positif perdu.
    person = _person(surname="Dufour", given="Guillaume-Henri")
    rows = [{"item": "http://www.wikidata.org/entity/Q99",
             "itemLabel": "Guillaume Henri Dufour",
             "birthDate": "1677-07-15T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    assert "nom" in pistes_wikidata(person, rows)[0].concordances


def test_accents_ne_font_pas_diverger_les_prenoms():
    # L'arbre porte 'Andre' comme 'André' : norm_nom les rejoint.
    person = _person(surname="Soulat", given="Andre")
    rows = [{"item": "http://www.wikidata.org/entity/Q99", "itemLabel": "André Soulat",
             "birthDate": "1677-07-15T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    assert "nom" in pistes_wikidata(person, rows)[0].concordances


def test_piste_forte_nom_date_complete_et_lieu():
    rows = [{"item": "http://www.wikidata.org/entity/Q42",
             "itemLabel": "Jean Dupont",
             "birthDate": "1677-07-15T00:00:00Z",
             "birthPlaceLabel": "Montbéliard"}]
    pistes = pistes_wikidata(_person(), rows)
    assert len(pistes) == 1
    p = pistes[0]
    assert p.source == "wikidata" and p.identite == "Q42"
    assert p.url == "http://www.wikidata.org/entity/Q42"
    assert set(p.concordances) == {"nom", "date complète", "lieu"}
    assert p.force == "forte"


def test_date_divergente_rend_la_piste_faible():
    rows = [{"item": "http://www.wikidata.org/entity/Q42", "itemLabel": "Jean Dupont",
             "birthDate": "1680-01-02T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    p = pistes_wikidata(_person(), rows)[0]
    assert "dates de naissance différentes" in p.divergences
    assert p.force == "faible"


def test_annee_seule_dans_l_arbre_ne_compte_pas_comme_date():
    person = _person(dateval=[0, 0, 1677, False])
    rows = [{"item": "http://www.wikidata.org/entity/Q42", "itemLabel": "Jean Dupont",
             "birthDate": "1677-07-15T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    p = pistes_wikidata(person, rows)[0]
    assert "date complète" not in p.concordances


def test_lieu_absent_de_l_arbre_ne_compte_pas():
    person = _person(place_name="")
    rows = [{"item": "http://www.wikidata.org/entity/Q42", "itemLabel": "Jean Dupont",
             "birthDate": "1677-07-15T00:00:00Z", "birthPlaceLabel": "Montbéliard"}]
    p = pistes_wikidata(person, rows)[0]
    assert "lieu" not in p.concordances


def test_aucun_resultat_rend_liste_vide():
    assert pistes_wikidata(_person(), []) == []
