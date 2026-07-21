# tests/test_genealogy_referentiel_mapper.py
"""Les cinq règles du mapper, sur les cas réels relevés sur Wikidata le 2026-07-21."""
from crewai_custom_tools.tools.genealogy.referentiel.config import PAYS_REFERENTIEL
from crewai_custom_tools.tools.genealogy.referentiel.wikidata import map_subdivisions

FR = PAYS_REFERENTIEL["FR"]
IT = PAYS_REFERENTIEL["IT"]
PL = PAYS_REFERENTIEL["PL"]
CH = PAYS_REFERENTIEL["CH"]

ENTITE = "http://www.wikidata.org/entity/"


def ligne(qid, label, iso, parent=None, coord=None, art=None, nom_local=None):
    """Une ligne aplatie telle que sparql_rows la rend (clés absentes si non liées)."""
    r = {"item": ENTITE + qid, "itemLabel": label, "iso": iso}
    if parent:
        r["parent"] = ENTITE + parent
    if coord:
        r["coord"] = coord
    if art:
        r["art"] = art
    if nom_local:
        r["nomLocal"] = nom_local
    return r


def test_les_noms_dapariement_portent_le_francais_puis_le_vernaculaire():
    DE = PAYS_REFERENTIEL["DE"]
    rows = [ligne("Q980", "Bavière", "DE-BY", parent="Q183", nom_local="Bayern")]
    subs, _ = map_subdivisions(rows, DE)
    assert subs[0].libelle_fr == "Bavière"
    assert subs[0].noms == ["Bavière", "Bayern"]


def test_les_noms_ne_repetent_pas_un_libelle_identique():
    rows = [ligne("Q1273", "Vaud", "CH-VD", parent="Q39", nom_local="Vaud")]
    subs, _ = map_subdivisions(rows, CH)
    assert subs[0].noms == ["Vaud"]


def test_niveau_1_quand_le_parent_est_le_pays():
    rows = [ligne("Q1273", "Vaud", "CH-VD", parent="Q39",
                  coord="Point(6.6 46.6)", art="https://fr.wikipedia.org/wiki/Canton_de_Vaud")]
    subs, collisions = map_subdivisions(rows, CH)
    assert collisions == []
    assert len(subs) == 1
    s = subs[0]
    assert (s.qid, s.iso, s.code, s.niveau) == ("Q1273", "CH-VD", "VD", 1)
    assert s.place_type == "State"          # jamais "Canton" : type natif seulement
    assert s.parent_qid == "Q39"
    assert (s.lat, s.long) == ("46.6", "6.6")   # WKT = Point(lon lat), ne pas inverser
    assert s.frwiki == "https://fr.wikipedia.org/wiki/Canton_de_Vaud"


def test_niveau_2_quand_le_parent_est_une_subdivision_de_niveau_1():
    rows = [ligne("Q18338206", "Auvergne-Rhône-Alpes", "FR-ARA", parent="Q142"),
            ligne("Q12549", "Allier", "FR-03", parent="Q18338206")]
    subs, _ = map_subdivisions(rows, FR)
    par_iso = {s.iso: s for s in subs}
    assert par_iso["FR-ARA"].niveau == 1 and par_iso["FR-ARA"].place_type == "Region"
    assert par_iso["FR-03"].niveau == 2 and par_iso["FR-03"].place_type == "Department"
    assert par_iso["FR-03"].code == "03"     # la convention de l'arbre


def test_parent_hors_ensemble_et_different_du_pays_ecarte_lentite():
    # IT-82 : Q134470541, sans libellé, rattachée à une commune. Règle 2.
    rows = [ligne("Q1460", "Sicile", "IT-82", parent="Q38"),
            ligne("Q134470541", "Q134470541", "IT-82", parent="Q31151")]
    subs, collisions = map_subdivisions(rows, IT)
    assert [s.qid for s in subs] == ["Q1460"]
    assert collisions == []                  # une seule retenue : pas de collision


def test_un_parent_de_niveau_2_donne_un_niveau_3_donc_ecarte():
    # IT-VE : Venise la ville pend sous la ville métropolitaine, qui pend sous la Vénétie.
    rows = [ligne("Q1225", "Vénétie", "IT-34", parent="Q38"),
            ligne("Q3678587", "ville métropolitaine de Venise", "IT-VE", parent="Q1225"),
            ligne("Q641", "Venise", "IT-VE", parent="Q3678587")]
    subs, collisions = map_subdivisions(rows, IT)
    assert sorted(s.qid for s in subs) == ["Q1225", "Q3678587"]
    assert collisions == []


def test_niveau_superieur_aux_niveaux_configures_ecarte():
    # PL-KI : Kielce, une ville sous une voïvodie. La Pologne n'a qu'un niveau.
    rows = [ligne("Q54193", "voïvodie de Sainte-Croix", "PL-26", parent="Q36"),
            ligne("Q102317", "Kielce", "PL-KI", parent="Q54193")]
    subs, _ = map_subdivisions(rows, PL)
    assert [s.iso for s in subs] == ["PL-26"]


def test_deux_entites_retenues_sous_un_meme_iso_font_une_collision_sans_ecriture():
    # FR-69 : le département et la circonscription départementale, même code, même niveau.
    rows = [ligne("Q18338206", "Auvergne-Rhône-Alpes", "FR-ARA", parent="Q142"),
            ligne("Q46130", "Rhône", "FR-69", parent="Q18338206"),
            ligne("Q18914778", "Rhône", "FR-69", parent="Q18338206")]
    subs, collisions = map_subdivisions(rows, FR)
    assert [s.iso for s in subs] == ["FR-ARA"]     # ni l'une ni l'autre n'est écrite
    assert len(collisions) == 1
    assert collisions[0].iso == "FR-69"
    assert sorted(collisions[0].qids) == ["Q18914778", "Q46130"]


def test_un_parent_de_meme_code_iso_que_lenfant_est_ignore():
    # Sans cette exclusion, Q46130 et Q18914778 se prendraient mutuellement pour parent.
    rows = [ligne("Q18338206", "Auvergne-Rhône-Alpes", "FR-ARA", parent="Q142"),
            ligne("Q46130", "Rhône", "FR-69", parent="Q18914778"),
            ligne("Q46130", "Rhône", "FR-69", parent="Q18338206")]
    subs, _ = map_subdivisions(rows, FR)
    assert {s.iso: s.niveau for s in subs} == {"FR-ARA": 1, "FR-69": 2}


def test_les_p131_historiques_sont_neutralises_par_labsence_de_lentite_dissoute():
    # Rhône-Alpes est dissoute : la requête ne la rend pas, elle n'est donc pas candidate.
    rows = [ligne("Q18338206", "Auvergne-Rhône-Alpes", "FR-ARA", parent="Q142"),
            ligne("Q12549", "Allier", "FR-03", parent="Q3084"),      # Rhône-Alpes, absente
            ligne("Q12549", "Allier", "FR-03", parent="Q18338206")]
    subs, _ = map_subdivisions(rows, FR)
    assert {s.iso: s.parent_qid for s in subs} == {"FR-ARA": "Q142", "FR-03": "Q18338206"}


def test_une_entite_sans_aucun_parent_est_ecartee():
    rows = [ligne("Q999999", "orpheline", "FR-99")]
    subs, collisions = map_subdivisions(rows, FR)
    assert subs == [] and collisions == []


def test_coordonnees_absentes_ne_font_pas_echouer():
    rows = [ligne("Q1273", "Vaud", "CH-VD", parent="Q39")]
    subs, _ = map_subdivisions(rows, CH)
    assert subs[0].lat is None and subs[0].long is None
