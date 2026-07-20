from crewai_custom_tools.tools.genealogy.models.domain import EventFact, PersonFacts
from crewai_custom_tools.tools.genealogy.pistes import pistes_dhs


def _person():
    birth = EventFact(type="Birth", year=1800, dateval=[3, 4, 1800, False],
                      place_name="Lausanne", place="Lausanne, Vaud, Suisse")
    return PersonFacts(gramps_id="I0500", handle="H5", name="Louis Perret",
                       surname="Perret", given="Louis", sex="M", birth=birth)


def test_ligne_sans_p902_ne_produit_aucune_piste():
    rows = [{"item": "http://www.wikidata.org/entity/Q42", "itemLabel": "Louis Perret",
             "birthDate": "1800-04-03T00:00:00Z", "birthPlaceLabel": "Lausanne"}]
    assert pistes_dhs(_person(), rows) == []


def test_ligne_avec_p902_produit_une_piste_dhs():
    rows = [{"item": "http://www.wikidata.org/entity/Q42", "itemLabel": "Louis Perret",
             "birthDate": "1800-04-03T00:00:00Z", "birthPlaceLabel": "Lausanne",
             "p902": "012345"}]
    pistes = pistes_dhs(_person(), rows)
    assert len(pistes) == 1
    p = pistes[0]
    assert p.source == "dhs"
    assert p.identite == "012345"
    assert p.url == "https://hls-dhs-dss.ch/fr/articles/012345/"
    # Les concordances sont héritées de la ligne Wikidata dont elle dérive.
    assert set(p.concordances) == {"nom", "date complète", "lieu"}
    assert p.force == "forte"


def test_lignes_melangees_ne_decale_pas_les_identifiants_dhs():
    """Preuve anti-appariement positionnel.

    Trois lignes, dans cet ordre : (1) sans P902 -> ignorée ; (2) avec P902
    mais sans URI exploitable -> ignorée aussi (comme `pistes_wikidata` le
    ferait) ; (3) avec P902 ET une URI valide -> seule ligne productrice.

    Si `pistes_dhs` appariait un jour les deux listes par position (un `zip`
    entre `resultats` et `pistes_wikidata(...)`) au lieu de dériver ligne par
    ligne, l'identifiant DHS de la ligne 2 ("999999", jamais censé sortir)
    se retrouverait collé à la piste réellement produite. Des identifiants
    P902 distincts entre les lignes 2 et 3 rendent ce décalage détectable :
    seul `identite == "012345"` (celui de la ligne 3) doit sortir.
    """
    rows = [
        # 1. Sans P902 : ignorée.
        {"item": "http://www.wikidata.org/entity/Q1", "itemLabel": "Louis Perret",
         "birthDate": "1800-04-03T00:00:00Z", "birthPlaceLabel": "Lausanne"},
        # 2. P902 présent mais URI inexploitable (clé "item" absente) : ignorée.
        {"itemLabel": "Louis Perret", "birthDate": "1800-04-03T00:00:00Z",
         "birthPlaceLabel": "Lausanne", "p902": "999999"},
        # 3. P902 présent et URI valide : seule ligne qui doit produire une piste.
        {"item": "http://www.wikidata.org/entity/Q42", "itemLabel": "Louis Perret",
         "birthDate": "1800-04-03T00:00:00Z", "birthPlaceLabel": "Lausanne",
         "p902": "012345"},
    ]
    pistes = pistes_dhs(_person(), rows)
    assert len(pistes) == 1
    assert pistes[0].identite == "012345"


def test_ligne_avec_p902_mais_rien_qui_concorde_ne_produit_aucune_piste():
    # Découle du correctif dans pistes_wikidata : une ligne P902 dont le nom, la
    # date et le lieu ne concordent avec rien dans l'arbre n'est pas une piste,
    # même si elle porte un identifiant DHS.
    rows = [{"item": "http://www.wikidata.org/entity/Q999",
             "itemLabel": "Marguerite Lefebvre",
             "birthDate": "1901-01-01T00:00:00Z",
             "birthPlaceLabel": "Marseille",
             "p902": "999999"}]
    assert pistes_dhs(_person(), rows) == []
