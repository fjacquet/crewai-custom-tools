# tests/test_genealogy_referentiel_mapper.py
"""Le mapper, éprouvé sur des charges Wikidata RÉELLES figées.

Les fixtures viennent de `scripts/capturer_charges_referentiel.py`. Tout QID désignant une
entité réelle a été vérifié en ligne le 2026-07-22 — libellé ET code `P300` relus via
`wbgetentities`, jamais de mémoire. Une version antérieure de ces tests portait des QID
inventés et n'a pas vu que la France entière tombait. Seuls les tests de cycle et d'orpheline
emploient des identifiants délibérément fictifs (`Q1`, `Q2`, `Q888888`, `Q999999`) : ils ne
désignent personne, et c'est exactement ce qu'ils éprouvent.
"""
import json
import pathlib

import pytest

from crewai_custom_tools.tools.genealogy.referentiel.config import PAYS_REFERENTIEL
from crewai_custom_tools.tools.genealogy.referentiel.wikidata import map_subdivisions

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "referentiel"
ENTITE = "http://www.wikidata.org/entity/"


def charge(code: str) -> list[dict]:
    return json.loads((FIXTURES / f"{code}.json").read_text(encoding="utf-8"))


def ligne(qid, label, iso, parent=None, coord=None, art=None, nom_local=None, ancre=False):
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
    if ancre:
        r["ancre"] = "true"
    return r


# --- charges réelles : ce que les fixtures écrites à la main ne pouvaient pas voir ---

def test_la_france_ne_se_reduit_pas_a_loutre_mer():
    """Régression : les régions métropolitaines pendent sous Q212429 France métropolitaine,
    qui n'a pas de code ISO. Sans l'ancre pays, 12 entités survivaient sur 125."""
    subs, collisions, ecartees = map_subdivisions(charge("FR"), PAYS_REFERENTIEL["FR"])
    assert len(subs) > 110
    niveaux = {n: sum(1 for s in subs if s.niveau == n) for n in (1, 2)}
    assert niveaux[1] > 20 and niveaux[2] > 90
    codes = {s.code for s in subs}
    assert {"ARA", "01", "75"} & codes           # au moins une région et un département


def test_la_collision_fr_69_est_signalee_sur_la_charge_reelle():
    """Le département du Rhône et la circonscription départementale partagent FR-69."""
    subs, collisions, _ = map_subdivisions(charge("FR"), PAYS_REFERENTIEL["FR"])
    fr69 = [c for c in collisions if c.iso == "FR-69"]
    assert len(fr69) == 1
    assert sorted(fr69[0].qids) == ["Q18914778", "Q46130"]
    assert "FR-69" not in {s.iso for s in subs}   # aucune des deux n'est écrite


def test_litalie_garde_ses_villes_metropolitaines_et_ecarte_le_reste():
    subs, collisions, ecartees = map_subdivisions(charge("IT"), PAYS_REFERENTIEL["IT"])
    par_iso = {s.iso: s for s in subs}
    assert par_iso["IT-NA"].place_type == "Province"     # Naples, ville métropolitaine
    assert par_iso["IT-MI"].place_type == "Province"     # Milan, idem
    assert par_iso["IT-25"].place_type == "Region"       # Lombardie
    assert par_iso["IT-VE"].qid == "Q3678587"            # la ville métropolitaine, pas la ville
    assert collisions == []
    ecartes = {e.iso for e in ecartees}
    assert {"IT-VE", "IT-82"} <= ecartes                 # Venise-ville et l'entité sans libellé


def test_la_suisse_rend_ses_26_cantons_en_type_natif():
    subs, collisions, _ = map_subdivisions(charge("CH"), PAYS_REFERENTIEL["CH"])
    assert len(subs) == 26
    assert {s.place_type for s in subs} == {"State"}
    assert collisions == []


def test_la_pologne_ecarte_la_ville_de_kielce():
    subs, _, ecartees = map_subdivisions(charge("PL"), PAYS_REFERENTIEL["PL"])
    assert len(subs) == 16
    assert "PL-KI" in {e.iso for e in ecartees}


@pytest.mark.parametrize("code", ["FR", "IT", "CH", "PL"])
def test_toute_entite_est_retenue_ecartee_ou_en_collision(code):
    """Les trois listes PARTITIONNENT la charge : ni disparition muette, ni entité comptée
    deux fois. Comparer des ensembles ne prouverait que l'union — les effectifs prouvent
    qu'aucune entité ne figure à la fois en retenue et en écartée."""
    rows = charge(code)
    subs, collisions, ecartees = map_subdivisions(rows, PAYS_REFERENTIEL[code])
    entrees = {r["item"].rsplit("/", 1)[-1] for r in rows}
    sorties = ([s.qid for s in subs] + [e.qid for e in ecartees]
               + [q for c in collisions for q in c.qids])
    assert set(sorties) == entrees
    assert len(sorties) == len(entrees)


@pytest.mark.parametrize("code", ["FR", "IT"])
def test_le_resultat_ne_depend_pas_de_lordre_des_lignes(code):
    """SPARQL ne garantit pas l'ordre. Les TROIS listes doivent être identiques d'une
    permutation à l'autre, écartées comprises : c'est là que se verrait une propriété
    multivaluée — deux P625 sur la même entité — retenue selon l'ordre d'arrivée."""
    import random

    rows = charge(code)
    pays = PAYS_REFERENTIEL[code]

    def sortie(lignes):
        return [[m.model_dump() for m in liste] for liste in map_subdivisions(lignes, pays)]

    reference = sortie(rows)
    alea = random.Random(1789)
    for _ in range(5):
        melange = list(rows)
        alea.shuffle(melange)
        assert sortie(melange) == reference


def test_les_coordonnees_ne_sont_pas_inversees():
    """WKT = Point(lon lat). Venise est à 45.4 N, 12.3 E — pas l'inverse."""
    subs, _, _ = map_subdivisions(charge("IT"), PAYS_REFERENTIEL["IT"])
    venise = next(s for s in subs if s.iso == "IT-VE")
    assert venise.lat.startswith("45.")
    assert venise.long.startswith("12.")


# --- cas qu'une charge réelle ne contient pas, en lignes vérifiées à la main ---

def test_charge_vide():
    subs, collisions, ecartees = map_subdivisions([], PAYS_REFERENTIEL["FR"])
    assert (subs, collisions, ecartees) == ([], [], [])


def test_un_cycle_de_rattachement_ecarte_les_deux_entites():
    """A parent de B, B parent de A : sans garde, la récursion ne terminerait pas."""
    rows = [ligne("Q1", "A", "FR-01", parent="Q2"),
            ligne("Q2", "B", "FR-02", parent="Q1")]
    subs, _, ecartees = map_subdivisions(rows, PAYS_REFERENTIEL["FR"])
    assert subs == []
    assert {e.iso for e in ecartees} == {"FR-01", "FR-02"}


def test_le_parent_le_moins_profond_lemporte():
    """Le Bas-Rhin pend sous la Collectivité européenne d'Alsace ET sous le Grand Est.
    Le rattachement direct fait foi, sinon il tomberait au niveau 3 et serait écarté.

    QID relus le 2026-07-22 : Q18677983 = Grand Est (FR-GES), Q2982948 = Collectivité
    européenne d'Alsace (FR-6AE), Q12717 = Bas-Rhin (FR-67). C'est la topologie réelle de
    la charge française, où le Bas-Rhin porte bien ces deux P131."""
    rows = [ligne("Q18677983", "Grand Est", "FR-GES", parent="Q212429", ancre=True),
            ligne("Q2982948", "Collectivité européenne d'Alsace", "FR-6AE",
                  parent="Q18677983"),
            ligne("Q12717", "Bas-Rhin", "FR-67", parent="Q2982948"),
            ligne("Q12717", "Bas-Rhin", "FR-67", parent="Q18677983")]
    subs, _, _ = map_subdivisions(rows, PAYS_REFERENTIEL["FR"])
    assert {s.iso: s.niveau for s in subs} == {"FR-GES": 1, "FR-6AE": 2, "FR-67": 2}
    # Le parent inscrit est celui qui a donné le niveau : le Grand Est, pas la Collectivité.
    assert {s.iso: s.parent_qid for s in subs} == {
        "FR-GES": "Q142", "FR-6AE": "Q18677983", "FR-67": "Q18677983"}


def test_lancre_ne_rattrape_pas_une_entite_dont_un_parent_est_dans_lunivers():
    """Venise-ville : son seul parent porte le même code ISO qu'elle, donc n'est pas
    candidat — mais il est dans l'univers, donc l'ancre ne doit pas la promouvoir."""
    rows = [ligne("Q1243", "Vénétie", "IT-34", parent="Q38", ancre=True),
            ligne("Q3678587", "ville métropolitaine de Venise", "IT-VE", parent="Q1243"),
            ligne("Q641", "Venise", "IT-VE", parent="Q3678587", ancre=True)]
    subs, collisions, ecartees = map_subdivisions(rows, PAYS_REFERENTIEL["IT"])
    assert sorted(s.qid for s in subs) == ["Q1243", "Q3678587"]
    assert collisions == []
    assert [e.qid for e in ecartees] == ["Q641"]


def test_un_parent_de_meme_code_iso_nest_jamais_candidat():
    """Sans cette clause, les deux FR-69 se prennent mutuellement pour parent et l'une
    est écrite seule, sans collision signalée."""
    rows = [ligne("Q18338206", "Auvergne-Rhône-Alpes", "FR-ARA", parent="Q212429", ancre=True),
            ligne("Q46130", "Rhône", "FR-69", parent="Q18914778"),
            ligne("Q46130", "Rhône", "FR-69", parent="Q18338206"),
            ligne("Q18914778", "Rhône", "FR-69", parent="Q18338206")]
    subs, collisions, _ = map_subdivisions(rows, PAYS_REFERENTIEL["FR"])
    assert [s.iso for s in subs] == ["FR-ARA"]
    assert len(collisions) == 1 and collisions[0].qids == ["Q18914778", "Q46130"]


def test_les_noms_dapariement_portent_le_francais_puis_le_vernaculaire():
    rows = [ligne("Q980", "Bavière", "DE-BY", parent="Q183", nom_local="Bayern", ancre=True)]
    subs, _, _ = map_subdivisions(rows, PAYS_REFERENTIEL["DE"])
    assert subs[0].noms == ["Bavière", "Bayern"]


def test_les_noms_ne_repetent_pas_un_libelle_identique():
    # Q12771 = canton de Vaud (CH-VD), relu le 2026-07-22.
    rows = [ligne("Q12771", "Vaud", "CH-VD", parent="Q39", nom_local="Vaud", ancre=True)]
    subs, _, _ = map_subdivisions(rows, PAYS_REFERENTIEL["CH"])
    assert subs[0].noms == ["Vaud"]


def test_une_entite_sans_parent_ni_ancre_est_ecartee_avec_son_motif():
    rows = [ligne("Q999999", "orpheline", "FR-99", parent="Q888888")]
    subs, collisions, ecartees = map_subdivisions(rows, PAYS_REFERENTIEL["FR"])
    assert subs == [] and collisions == []
    assert ecartees[0].iso == "FR-99"
    assert ecartees[0].motif                      # un motif non vide, lisible par un humain
