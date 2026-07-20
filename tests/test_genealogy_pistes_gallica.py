from crewai_custom_tools.tools.genealogy.models.domain import EventFact, PersonFacts
from crewai_custom_tools.tools.genealogy.pistes import (
    dates_du_texte, fenetre_vie, personne_eligible, pistes_gallica, requete_gallica,
)


def _person(dateval=None, place_name="Montbéliard", deces_annee=None):
    birth = EventFact(type="Birth", year=1900, dateval=dateval or [14, 7, 1900, False],
                      place_name=place_name,
                      place=f"{place_name}, Doubs, France" if place_name else "")
    death = (EventFact(type="Death", year=deces_annee,
                       dateval=[1, 1, deces_annee, False]) if deces_annee else None)
    return PersonFacts(gramps_id="I0042", handle="H42", name="Jean Dupont",
                       surname="Dupont", given="Jean", sex="M", birth=birth, death=death)


def test_personne_sans_lieu_est_ineligible():
    assert personne_eligible(_person(place_name="")) is False


def test_personne_sans_date_complete_est_ineligible():
    assert personne_eligible(_person(dateval=[0, 0, 1900, False])) is False


def test_personne_datee_et_localisee_est_eligible():
    assert personne_eligible(_person()) is True


def test_fenetre_sans_deces_borne_a_cent_cinq_ans():
    assert fenetre_vie(_person()) == (1900, 2005)


def test_fenetre_avec_deces_utilise_l_annee_du_deces():
    assert fenetre_vie(_person(deces_annee=1970)) == (1900, 1970)


def test_requete_contient_nom_et_lieu():
    q = requete_gallica(_person())
    assert "Dupont" in q and "Montbéliard" in q


def test_resultat_hors_fenetre_est_ecarte():
    records = [{"title": "Le Journal", "creator": "", "date": "2020",
                "type": "text", "url": "https://gallica.bnf.fr/ark:/12148/bpt6k1"}]
    assert pistes_gallica(_person(deces_annee=1970), records) == []


def test_resultat_dans_la_fenetre_donne_une_piste_faible():
    records = [{"title": "Le Journal de Montbéliard", "creator": "", "date": "1935",
                "type": "text", "url": "https://gallica.bnf.fr/ark:/12148/bpt6k1"}]
    pistes = pistes_gallica(_person(deces_annee=1970), records)
    assert len(pistes) == 1
    p = pistes[0]
    assert p.source == "gallica"
    assert p.identite == "ark:/12148/bpt6k1"
    assert p.identite_derivee is False
    assert p.url == "https://gallica.bnf.fr/ark:/12148/bpt6k1"
    assert p.force == "faible"


def test_nom_et_lieu_dans_le_meme_titre_ne_font_qu_un_facteur():
    """Le titre est UNE preuve. Sans cette règle, « Le Journal de Montbéliard »
    rendrait FORTE une piste pour un Dupont né à Montbéliard — donc écrite
    dans l'arbre — sans qu'aucune identité n'ait été vérifiée."""
    records = [{"title": "Dupont et le Journal de Montbéliard", "creator": "",
                "date": "1935", "type": "text",
                "url": "https://gallica.bnf.fr/ark:/12148/bpt6k1"}]
    p = pistes_gallica(_person(deces_annee=1970), records)[0]
    assert len(set(p.concordances)) == 1
    assert p.force == "faible"


def test_titre_portant_la_date_complete_atteint_forte():
    records = [{"title": "Dupont — acte du 14 juillet 1900", "creator": "",
                "date": "1935", "type": "text",
                "url": "https://gallica.bnf.fr/ark:/12148/bpt6k1"}]
    p = pistes_gallica(_person(deces_annee=1970), records)[0]
    assert set(p.concordances) == {"nom", "date complète"}
    assert p.force == "forte"


def test_roy_ne_correspond_pas_a_leroy_dans_un_titre():
    person = _person(dateval=[14, 7, 1900, False], place_name="Montbéliard")
    person.surname = "Roy"
    records = [{"title": "Le Leroy de Belfort", "creator": "", "date": "1935",
                "type": "text", "url": "https://gallica.bnf.fr/ark:/12148/bpt6k1"}]
    assert pistes_gallica(person, records)[0].concordances == []


def test_annee_seule_dans_le_titre_n_est_pas_une_date():
    assert dates_du_texte("Le Journal de 1900") == set()
    assert dates_du_texte("acte du 14/07/1900") == {"1900-07-14"}
    assert dates_du_texte("acte du 1900-07-14") == {"1900-07-14"}


def test_personne_ineligible_ne_produit_rien():
    records = [{"title": "Le Journal", "creator": "", "date": "1935",
                "type": "text", "url": "https://gallica.bnf.fr/ark:/12148/bpt6k1"}]
    assert pistes_gallica(_person(place_name=""), records) == []


def test_resultat_sans_ark_est_ecarte():
    # Jamais d'URL fabriquée : sans permalien, pas de piste.
    records = [{"title": "Le Journal", "creator": "", "date": "1935",
                "type": "text", "url": ""}]
    assert pistes_gallica(_person(), records) == []
