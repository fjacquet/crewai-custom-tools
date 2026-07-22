"""Tests de la détection pure des doublons de lieux."""

import pytest

from crewai_custom_tools.tools.genealogy.analysis.place_duplicates import (
    PREUVE_CODE,
    PREUVE_COORDONNEES,
    choisir_survivant,
    etager_lieux,
    evaluer_preuve,
    normaliser_nom_lieu,
    perte_evitee,
    richesse,
)
from crewai_custom_tools.tools.genealogy.models.domain import PlaceFacts


def test_casse_accents_et_separateurs_convergent():
    assert normaliser_nom_lieu("Saint-Palais") == normaliser_nom_lieu("SAINT PALAIS")
    assert normaliser_nom_lieu("Nohant-en-Goût") == normaliser_nom_lieu("nohant en gout")


def test_apostrophe_typographique_equivaut_a_l_ascii():
    """L'apostrophe courbe est l'usage typographique standard ; elle arrive par copier-coller."""
    assert normaliser_nom_lieu("L'Isle-Adam") == normaliser_nom_lieu("L’Isle-Adam")


def test_ligature_oe_equivaut_a_oe():
    """NFD décompose les accents, pas les ligatures. Vœuil-et-Giget (Charente) et
    Œuilly (Aisne) sont des communes réelles ; Ænes est un hameau norvégien réel —
    la ligature en minuscule (œ) et en majuscule (Œ, Æ) doit converger avec sa forme
    dépliée (« oe », « OE », « ae », « AE »)."""
    assert normaliser_nom_lieu("Vœuil-et-Giget") == normaliser_nom_lieu("Voeuil-et-Giget")
    assert normaliser_nom_lieu("Œuilly") == normaliser_nom_lieu("Oeuilly")
    assert normaliser_nom_lieu("Ænes") == normaliser_nom_lieu("Aenes")


def test_lettre_barree_ne_converge_pas_avec_sa_transliteration():
    """La table _LIGATURES couvre les ligatures (œ, æ), pas les lettres barrées.
    ø/Ø est une lettre scandinave à part entière, qu'Unicode ne décompose pas et
    qui n'est ni un accent ni une ligature composée. La transformer en "o" serait
    un choix arbitraire : rien ne justifierait alors d'ignorer le ł polonais ou le
    đ croate. Décision délibérée : les lettres barrées restent hors du périmètre
    de cette table, et Tønder ne doit pas s'y confondre avec Tonder."""
    assert normaliser_nom_lieu("Tønder") != normaliser_nom_lieu("Tonder")


def test_l_apostrophe_reste_un_separateur_et_ne_disparait_pas():
    """Si l'apostrophe était supprimée au lieu d'être séparée, deux communes
    distinctes se confondraient."""
    assert normaliser_nom_lieu("L'Isle-Adam") != normaliser_nom_lieu("Lisle-Adam")


def test_chaine_vide_et_blancs():
    assert normaliser_nom_lieu("") == ""
    assert normaliser_nom_lieu("   ") == ""


def _lieu(gid, **kw):
    base = {"gramps_id": gid, "handle": "H" + gid, "nom": "X"}
    base.update(kw)
    return PlaceFacts(**base)


def test_codes_identiques_prouvent_quel_que_soit_le_type():
    """Un code officiel est un identifiant canonique, pas une ressemblance."""
    a = _lieu("P1", code="18044", place_type="Municipality")
    b = _lieu("P2", code="18044", place_type="City")
    assert evaluer_preuve(a, b) == "code"


def test_codes_differents_opposent_un_veto():
    """Paris : Department 75 contre Municipality 75056 — deux entités réelles."""
    a = _lieu("P0301", code="75", place_type="Department", lat="48.8589", long="2.347")
    b = _lieu("P0008", code="75056", place_type="Municipality", lat="48.8589", long="2.347")
    assert evaluer_preuve(a, b) == ""


def test_codes_differents_a_type_egal_et_coordonnees_egales_ne_prouvent_pas():
    """Le veto est ici la SEULE garde : ni le type ni la position ne discriminent.

    Deux Saint-Palais réels — 18205 dans le Cher, 17398 en Charente-Maritime —
    tous deux `Municipality`, tous deux portant le même point (un géocodage
    approximatif ou un copier-coller de coordonnées suffit à produire ce cas).
    Le type étant identique, la garde de type laisse passer ; les coordonnées
    étant complètes et égales, la voie des coordonnées conclurait. Seul le veto
    des codes officiels distincts empêche alors une fusion irréversible.

    Configuration programmée, pas hypothétique : le chantier référentiel pose
    types ET coordonnées sur les contenants ; dès que les types sont
    uniformisés, la garde de type cesse de discriminer.
    """
    a = _lieu("P0205", code="18205", place_type="Municipality",
              lat="45.6533", long="-0.4869")
    b = _lieu("P0398", code="17398", place_type="Municipality",
              lat="45.6533", long="-0.4869")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_coordonnees_identiques_prouvent_a_type_egal():
    """Rhodt unter Rietburg : deux Municipality sans code, mêmes coordonnées."""
    a = _lieu("P0119", place_type="Municipality", lat="49.2708776", long="8.1234")
    b = _lieu("P0103", place_type="Municipality", lat="49.2708776", long="8.1234")
    assert evaluer_preuve(a, b) == "coordonnees"


def test_coordonnees_ne_prouvent_rien_entre_types_differents():
    """Le chantier référentiel va géocoder les départements : ce refus doit tenir."""
    a = _lieu("P0301", place_type="Department", lat="48.8589", long="2.347")
    b = _lieu("P0008", place_type="Municipality", lat="48.8589", long="2.347")
    assert evaluer_preuve(a, b) == ""


def test_un_seul_code_renseigne_ne_prouve_pas():
    """Annaba : Department sans code contre Wilaya code 23 — arbitrage humain."""
    a = _lieu("P0343", place_type="Department")
    b = _lieu("P0383", place_type="Wilaya", code="23")
    assert evaluer_preuve(a, b) == ""


def test_sans_code_ni_coordonnees_aucune_preuve():
    a = _lieu("P1", place_type="Municipality")
    b = _lieu("P2", place_type="Municipality")
    assert evaluer_preuve(a, b) == ""


def test_coordonnees_partielles_ne_prouvent_pas():
    """Une latitude égale et une longitude vide n'est pas une coïncidence de position."""
    a = _lieu("P1", place_type="Municipality", lat="47.1147")
    b = _lieu("P2", place_type="Municipality", lat="47.1147", long="2.0")
    assert evaluer_preuve(a, b) == ""


def test_meme_latitude_mais_longitude_differente_ne_prouve_pas():
    """La preuve porte sur le COUPLE, jamais sur la latitude seule.

    Deux communes entièrement géocodées peuvent partager une latitude au
    centième près sans partager la moindre position : le parallèle 47.11 traverse
    la France entière. Ne comparer que `lat` suffirait à faire fusionner
    automatiquement deux communes distinctes d'un même parallèle."""
    a = _lieu("P1", place_type="Municipality", lat="47.1147", long="2.0")
    b = _lieu("P2", place_type="Municipality", lat="47.1147", long="5.0")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_longitude_absente_des_deux_cotes_ne_prouve_pas():
    """Les couples sont ÉGAUX : seule l'exigence de complétude peut refuser.

    Deux `Municipality` de même latitude, sans longitude ni d'un côté ni de
    l'autre — l'état d'un géocodage à moitié importé. `(lat, long)` vaut
    `("47.1147", "")` des deux côtés, donc la comparaison des couples conclut à
    l'égalité : si la preuve se contentait d'« au moins une composante
    renseignée », deux communes dont on ignore la position fusionneraient.
    """
    a = _lieu("P1", place_type="Municipality", lat="47.1147")
    b = _lieu("P2", place_type="Municipality", lat="47.1147")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_meme_longitude_mais_latitude_differente_ne_prouve_pas():
    """Miroir du test précédent : la preuve porte sur le COUPLE, pas sur `long`.

    Deux communes homonymes peuvent partager un méridien sans partager la
    moindre position : à longitude 2.3988, la latitude 47.0810 est celle de
    Bourges et 48.8589 celle de Paris — deux cents kilomètres d'écart. Ne
    comparer que `long` les ferait fusionner automatiquement."""
    a = _lieu("P1", place_type="Municipality", lat="47.0810", long="2.3988")
    b = _lieu("P2", place_type="Municipality", lat="48.8589", long="2.3988")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


@pytest.mark.parametrize(
    ("type_a", "type_b"),
    [("Unknown", "Unknown"), ("", ""), ("", "Unknown"), ("Unknown", "Municipality")],
    ids=["deux-unknown", "deux-vides", "vide-contre-unknown", "unknown-contre-connu"],
)
def test_type_inconnu_ne_prouve_jamais_par_coordonnees(type_a, type_b):
    """L'ignorance n'est pas une valeur : un inconnu n'est égal à aucun autre.

    Scénario réel et programmé — le chantier référentiel va géocoder les
    contenants : un arrondissement « Bourges » encore sans type, géocodé au point
    de son chef-lieu, face à la commune « Bourges » sans type ni code. Même nom,
    aucun code pour opposer un veto, coordonnées identiques : si l'absence de
    type valait égalité de type, la fusion serait automatique et irréversible.

    Les deux orthographes de l'ignorance (`""` du modèle, `"Unknown"` de l'API)
    valent la même chose : le verdict ne doit pas dépendre de ce que rend l'API.
    """
    a = _lieu("P1", place_type=type_a, lat="47.0810", long="2.3988")
    b = _lieu("P2", place_type=type_b, lat="47.0810", long="2.3988")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_type_connu_reste_insensible_aux_blancs():
    """Le nettoyage des blancs ne doit pas casser la voie des coordonnées."""
    a = _lieu("P1", place_type=" Municipality ", lat=" 49.2708776 ", long=" 8.1234 ")
    b = _lieu("P2", place_type="Municipality", lat="49.2708776", long="8.1234")
    assert evaluer_preuve(a, b) == PREUVE_COORDONNEES
    assert evaluer_preuve(b, a) == PREUVE_COORDONNEES


@pytest.mark.parametrize(
    ("code_a", "code_b"),
    [(" ", " "), (" ", "  "), ("\t", " ")],
    ids=["memes-blancs", "blancs-de-longueurs-differentes", "tabulation-contre-espace"],
)
def test_codes_blancs_ne_prouvent_rien(code_a, code_b):
    """Un champ vidé en tapant une espace n'est pas un identifiant canonique.

    `" "` est truthy en Python ; sans nettoyage, deux codes blancs identiques se
    prouvent l'un l'autre — et le code prouve quel que soit le type, donc
    jusqu'entre un département et une commune."""
    a = _lieu("P0301", code=code_a, place_type="Department")
    b = _lieu("P0008", code=code_b, place_type="Municipality")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_code_blanc_ne_leve_pas_le_veto_ni_ne_prouve_face_a_un_vrai_code():
    """Un code blanc vaut un code absent : on retombe sur l'arbitrage humain."""
    a = _lieu("P1", code=" ", place_type="Municipality", lat="47.08", long="2.39")
    b = _lieu("P2", code="18033", place_type="Municipality", lat="47.08", long="2.39")
    assert evaluer_preuve(a, b) == PREUVE_COORDONNEES
    assert evaluer_preuve(b, a) == PREUVE_COORDONNEES


def test_coordonnees_blanches_ne_prouvent_rien():
    """Deux lieux « géocodés » à coups d'espaces ne partagent aucune position."""
    a = _lieu("P1", place_type="Municipality", lat=" ", long=" ")
    b = _lieu("P2", place_type="Municipality", lat="", long="")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_deux_contenants_connus_et_differents_interdisent_la_preuve_par_coordonnees():
    """C2 — deux entités distinctes sans code fusionnaient automatiquement.

    Deux « Saint-Michel », toutes deux `Municipality`, sans code officiel, aux
    coordonnées identiques — un géocodage approximatif ou un copier-coller de
    coordonnées suffit à produire ce cas — mais rattachées à DEUX DÉPARTEMENTS
    différents. Le discriminant existe dans l'arbre ; le modèle de faits l'avait
    réduit à un booléen « a un parent ou non », si bien que la voie des
    coordonnées concluait et que la fusion partait en automatique irréversible.

    Deux contenants connus et différents opposent donc un refus, exactement
    comme deux codes officiels différents.
    """
    a = _lieu("P1", place_type="Municipality", lat="47.1", long="2.3",
              parent_id="HD18")
    b = _lieu("P2", place_type="Municipality", lat="47.1", long="2.3",
              parent_id="HD37")
    assert evaluer_preuve(a, b) == ""
    assert evaluer_preuve(b, a) == ""


def test_le_meme_contenant_laisse_prouver_par_coordonnees():
    """La garde ne se déclenche que sur une DIFFÉRENCE : même département, même lieu."""
    a = _lieu("P1", place_type="Municipality", lat="47.1", long="2.3",
              parent_id="HD18")
    b = _lieu("P2", place_type="Municipality", lat="47.1", long="2.3",
              parent_id="HD18")
    assert evaluer_preuve(a, b) == PREUVE_COORDONNEES


@pytest.mark.parametrize(
    ("parent_a", "parent_b"),
    [("", ""), ("HD18", ""), ("", "HD18"), (" ", "HD18")],
    ids=["deux-inconnus", "connu-contre-inconnu", "inconnu-contre-connu",
         "blanc-contre-connu"],
)
def test_un_contenant_inconnu_n_interdit_pas_la_preuve_par_coordonnees(parent_a, parent_b):
    """L'ignorance n'est pas une différence : elle ne peut pas opposer de refus.

    Symétrique du traitement des codes — un code absent n'oppose aucun veto — et
    de celui des types, où l'inconnu ne PROUVE rien. Ici la garde est un refus,
    pas une preuve : la déclencher sur une non-mesure écarterait de vrais
    doublons, et le rattachement est absent d'une grande part de l'arbre.
    """
    a = _lieu("P1", place_type="Municipality", lat="47.1", long="2.3",
              parent_id=parent_a)
    b = _lieu("P2", place_type="Municipality", lat="47.1", long="2.3",
              parent_id=parent_b)
    assert evaluer_preuve(a, b) == PREUVE_COORDONNEES
    assert evaluer_preuve(b, a) == PREUVE_COORDONNEES


def test_deux_contenants_differents_n_empechent_pas_la_preuve_par_le_code():
    """La garde s'arrête à la voie des coordonnées : le code reste canonique.

    Une même commune peut être rattachée au département dans un enregistrement
    et à l'arrondissement dans l'autre — c'est un doublon de saisie, pas deux
    entités. Le code officiel prouve seul, et rien dans le rattachement ne le
    fragilise.
    """
    a = _lieu("P1", place_type="Municipality", code="18033", parent_id="HD18")
    b = _lieu("P2", place_type="Municipality", code="18033", parent_id="HARR")
    assert evaluer_preuve(a, b) == PREUVE_CODE
    assert evaluer_preuve(b, a) == PREUVE_CODE


_PAIRES_SYMETRIE = [
    # (a, b) couvrant chaque branche du verdict, dans les deux sens.
    (_lieu("P1", code="18044", place_type="Municipality"),
     _lieu("P2", code="18044", place_type="City")),
    (_lieu("P1", code="75", place_type="Department", lat="48.8589", long="2.347"),
     _lieu("P2", code="75056", place_type="Municipality", lat="48.8589", long="2.347")),
    # Le veto seul : même type connu, coordonnées complètes identiques — rien
    # d'autre que les codes distincts ne peut refuser, dans un sens comme dans
    # l'autre.
    (_lieu("P1", code="18205", place_type="Municipality", lat="45.6533", long="-0.4869"),
     _lieu("P2", code="17398", place_type="Municipality", lat="45.6533", long="-0.4869")),
    (_lieu("P1", place_type="Municipality", lat="49.27", long="8.12"),
     _lieu("P2", place_type="Municipality", lat="49.27", long="8.12")),
    (_lieu("P1", place_type="Department", lat="48.8589", long="2.347"),
     _lieu("P2", place_type="Municipality", lat="48.8589", long="2.347")),
    (_lieu("P1", place_type="Department"),
     _lieu("P2", place_type="Wilaya", code="23")),
    (_lieu("P1", place_type="Municipality", lat="47.1147"),
     _lieu("P2", place_type="Municipality", lat="47.1147", long="2.0")),
    (_lieu("P1", place_type="Municipality", lat="47.1147", long="2.0"),
     _lieu("P2", place_type="Municipality", lat="47.1147", long="5.0")),
    (_lieu("P1", place_type="Unknown", lat="47.08", long="2.39"),
     _lieu("P2", place_type="", lat="47.08", long="2.39")),
    # Coordonnées présentes à dessein : c'est la seule configuration où un côté
    # trancherait sur son propre code pendant que l'autre conclurait par la position.
    (_lieu("P1", code=" ", place_type="Municipality", lat="47.08", long="2.39"),
     _lieu("P2", code="18033", place_type="Municipality", lat="47.08", long="2.39")),
]


_IDS_SYMETRIE = [
    "codes-egaux", "codes-differents", "codes-differents-tout-le-reste-egal",
    "coordonnees-egales", "types-differents",
    "un-seul-code", "coordonnees-partielles", "longitudes-differentes",
    "types-inconnus", "code-blanc-contre-code",
]


@pytest.mark.parametrize(("a", "b"), _PAIRES_SYMETRIE, ids=_IDS_SYMETRIE)
def test_le_verdict_est_symetrique(a, b):
    """`evaluer_preuve` ne doit pas dépendre de l'ordre des deux lieux.

    L'appelant parcourt des paires non ordonnées ; une asymétrie ferait dépendre
    une fusion irréversible de l'ordre d'itération sur l'arbre — un lieu fusionné
    ou non selon la page d'API qui l'a rendu en premier."""
    assert evaluer_preuve(a, b) == evaluer_preuve(b, a)


def test_les_constantes_de_verdict_sont_les_valeurs_rendues():
    """Les deux verdicts sont exportés : l'appelant n'a pas à recopier de littéral."""
    assert (PREUVE_CODE, PREUVE_COORDONNEES) == ("code", "coordonnees")


def test_richesse_compte_les_attributs_renseignes():
    assert richesse(_lieu("P1")) == 0
    assert richesse(_lieu("P1", lat="47.1", long="2.3")) == 1
    assert richesse(_lieu("P1", lat="47.1", long="2.3", code="18044", a_parent=True)) == 3


def test_le_plus_riche_gagne_meme_avec_moins_de_retroliens():
    """C'est le cœur de la règle : garder la coquille vide effacerait ses coordonnées."""
    pauvre = _lieu("P0387", retroliens=50)
    riche = _lieu("P0148", lat="48.8467", long="5.6", code="55012", retroliens=1)
    assert choisir_survivant([pauvre, riche]).gramps_id == "P0148"


def test_a_richesse_egale_les_retroliens_departagent():
    a = _lieu("P0064", lat="47.1", long="2.3", code="18044", retroliens=53)
    b = _lieu("P0070", lat="47.1", long="2.3", code="18044", retroliens=4)
    assert choisir_survivant([a, b]).gramps_id == "P0064"


def test_a_egalite_complete_le_plus_petit_identifiant_tranche():
    """Quantilly : cinq événements de chaque côté, mêmes données. La règle reste totale."""
    a = _lieu("P0184", lat="47.2", long="2.5", code="18189", retroliens=5)
    b = _lieu("P0059", lat="47.2", long="2.5", code="18189", retroliens=5)
    assert choisir_survivant([a, b]).gramps_id == "P0059"


def test_survivant_sur_une_grappe_de_trois():
    a = _lieu("P0178", lat="45.6", long="6.4", code="73312", retroliens=4)
    b = _lieu("P0192", lat="45.6", long="6.4", code="73312", retroliens=19)
    c = _lieu("P0198", lat="45.6", long="6.4", code="73312", retroliens=5)
    assert choisir_survivant([a, b, c]).gramps_id == "P0192"


def test_perte_evitee_nomme_ce_qui_aurait_disparu():
    riche = _lieu("P0148", lat="48.8467", long="5.6", code="55012")
    pauvre = _lieu("P0387")
    assert perte_evitee(riche, pauvre) == ""          # rien à perdre dans ce sens
    texte = perte_evitee(pauvre, riche)
    assert "coordonnées" in texte and "code" in texte


def test_perte_evitee_vide_quand_les_deux_sont_egaux():
    a = _lieu("P1", lat="47.1", long="2.3", code="18044")
    b = _lieu("P2", lat="47.1", long="2.3", code="18044")
    assert perte_evitee(a, b) == ""


def test_richesse_ignore_les_champs_ne_contenant_que_des_blancs():
    """Un code et des coordonnées « effacés » en tapant une espace ne comptent pas.

    `" "` est truthy en Python : sans passer par `_renseigne` comme le fait
    `evaluer_preuve`, ce lieu afficherait une richesse de 2 alors qu'il ne porte
    aucune donnée exploitable."""
    vide_avec_espace = _lieu("P1", code=" ", lat=" ", long=" ")
    assert richesse(vide_avec_espace) == 0


def test_champ_blanc_ne_l_emporte_pas_sur_un_lieu_reellement_vide():
    """Miroir de `test_le_plus_riche_gagne_meme_avec_moins_de_retroliens` : une
    coquille dont le code et les coordonnées ne sont que des espaces ne doit pas
    se faire passer pour riche et l'emporter sur un doublon réellement vide mais
    davantage référencé. Sans le nettoyage, `choisir_survivant` désignerait P2
    (richesse apparente 2) au lieu de P1 (retroliens 50 contre 1) — et les vraies
    données de P1 (ici son poids dans l'arbre) seraient perdues au profit d'une
    coquille vide."""
    vrai_vide = _lieu("P1", retroliens=50)
    vide_avec_espace = _lieu("P2", code=" ", lat=" ", long=" ", retroliens=1)
    assert choisir_survivant([vrai_vide, vide_avec_espace]).gramps_id == "P1"


def test_perte_evitee_n_annonce_pas_une_perte_de_champs_blancs():
    """Le rapport lu par un humain ne doit pas annoncer la perte d'un code ou de
    coordonnées qui, sous les espaces, n'existaient pas."""
    vrai_vide = _lieu("P1")
    vide_avec_espace = _lieu("P2", code=" ", lat=" ", long=" ")
    assert perte_evitee(vrai_vide, vide_avec_espace) == ""


def test_richesse_exige_les_deux_coordonnees_jamais_une_seule():
    """Une latitude seule, sans longitude, ne prouve aucune position exploitable —
    la richesse doit rester à 0, pas remonter à 1 pour une coordonnée orpheline."""
    assert richesse(_lieu("P1", lat="47.1")) == 0
    assert richesse(_lieu("P1", long="2.3")) == 0


def test_perte_evitee_signale_le_type_manquant():
    """Branche « type » : l'absorbé est typé, le survivant ne l'est pas, rien
    d'autre (code, coordonnées) ne distingue les deux — seule la perte du type
    doit être rapportée.

    Remplace `test_perte_evitee_signale_le_rattachement_manquant`, qui exerçait
    la branche « rattachement » : celle-ci a disparu parce que la fusion Gramps
    unionne les listes de références, donc le rattachement SURVIT (voir la
    docstring de `perte_evitee`). Le type, lui, est un champ simple bel et bien
    écrasé — c'est la branche équivalente sur un attribut réellement détruit.
    """
    survivant = _lieu("P1", lat="47.1", long="2.3", code="18044", place_type="")
    absorbe = _lieu("P2", lat="47.1", long="2.3", code="18044",
                    place_type="Municipality")
    assert perte_evitee(survivant, absorbe) == "type"


def test_perte_evitee_signale_des_coordonnees_concurrentes():
    """C1 — deux coordonnées RENSEIGNÉES et différentes : la fusion en écrase une.

    La garde ne testait que présence contre absence. Or `lat`/`long` sont des
    champs simples : la fusion Gramps ne garde que ceux du survivant. Deux
    « Bourges » du même code, l'un géocodé grossièrement, l'autre au dix
    millième, ne se distinguent pas par une absence — et pourtant la position
    précise disparaît. Le sens est symétrique : quel que soit celui qu'on garde,
    l'autre valeur est détruite.
    """
    grossier = _lieu("P1", lat="47.1", long="2.4", code="18033")
    precis = _lieu("P2", lat="47.0810", long="2.3988", code="18033")
    assert perte_evitee(grossier, precis) == "coordonnées"
    assert perte_evitee(precis, grossier) == "coordonnées"


def test_perte_evitee_signale_un_type_concurrent():
    """C1 — deux types CONNUS et différents : le module refuse d'inférer entre eux…

    …mais acceptait d'en détruire un sur la voie du code. `evaluer_preuve` tient
    « Municipality » et « City » pour assez différents pour interdire toute
    preuve par coordonnées ; la fusion prouvée par le code, elle, écrasait
    silencieusement le second. Deux valeurs concurrentes sur un champ simple :
    c'est à un humain de trancher.
    """
    a = _lieu("P1", place_type="Municipality", code="18044")
    b = _lieu("P2", place_type="City", code="18044")
    assert perte_evitee(a, b) == "type"
    assert perte_evitee(b, a) == "type"


def test_perte_evitee_ne_double_pas_le_veto_sur_deux_codes_concurrents():
    """Décision délibérée : deux codes concurrents sont l'affaire du VETO, pas de la perte.

    Une paire dont les codes officiels s'opposent ne produit aucune proposition
    (D3) : elle n'atteint jamais le calcul de perte. Y ajouter une branche
    « code » pour valeurs différentes serait du code mort qui donnerait
    l'illusion d'une garde. La branche « code » reste donc présence contre
    absence, à la différence des coordonnées et du type.
    """
    a = _lieu("P1", code="18205", place_type="Municipality")
    b = _lieu("P2", code="17398", place_type="Municipality")
    assert perte_evitee(a, b) == ""
    assert perte_evitee(b, a) == ""


def test_la_richesse_ne_compte_pas_le_rattachement():
    """C1 — l'attribut qui ne risque rien ne doit pas désigner le survivant.

    `perte_evitee` explique elle-même que le rattachement est une LISTE de
    références, unionnée par la fusion Gramps, donc jamais détruite. Le compter
    dans la richesse faisait trancher le choix du survivant par le seul attribut
    qui ne se perd jamais, au détriment de ceux qui se perdent vraiment.
    """
    assert richesse(_lieu("P1", a_parent=True)) == 0
    assert richesse(_lieu("P1", lat="47.1", long="2.3", code="18044",
                          a_parent=True)) == 2


def test_perte_evitee_ignore_le_rattachement_que_la_fusion_conserve():
    """Le rattachement est une LISTE de références : Gramps l'unionne, donc il
    survit à la fusion. L'annoncer comme perdu ferait partir en relecture des
    fusions qui ne détruisent rien — et l'état « rattaché » est massivement
    répandu dans l'arbre réel."""
    survivant = _lieu("P1", lat="47.1", long="2.3", code="18044", a_parent=False)
    absorbe = _lieu("P2", lat="47.1", long="2.3", code="18044", a_parent=True)
    assert perte_evitee(survivant, absorbe) == ""


def _commune(gid, nom, **kw):
    base = {"gramps_id": gid, "handle": "H" + gid, "nom": nom,
            "place_type": "Municipality"}
    base.update(kw)
    return PlaceFacts(**base)


def test_un_lieu_unique_ne_produit_rien():
    assert etager_lieux([_commune("P1", "Vierzon", code="18279")]) == []


def test_deux_communes_meme_code_donnent_une_proposition_auto():
    props = etager_lieux([
        _commune("P0064", "Cerbois", code="18044", lat="47.1", long="2.3", retroliens=53),
        _commune("P0070", "Cerbois", code="18044", lat="47.1", long="2.3", retroliens=4),
    ])
    assert len(props) == 1
    p = props[0]
    assert p.verdict == "auto"
    assert (p.gramps_id_keep, p.gramps_id_merge) == ("P0064", "P0070")
    assert p.canonical == "Cerbois"
    assert "code" in p.reason


def test_noms_differents_ne_sont_pas_candidats():
    props = etager_lieux([
        _commune("P1", "Bourges", code="18033"),
        _commune("P2", "Vierzon", code="18279"),
    ])
    assert props == []


def test_types_differents_sans_code_partagent_le_nom_mais_partent_en_arbitrage():
    """Annaba : Department sans code contre Wilaya code 23."""
    props = etager_lieux([
        PlaceFacts(gramps_id="P0343", handle="HA", nom="Annaba", place_type="Department"),
        PlaceFacts(gramps_id="P0383", handle="HB", nom="Annaba", place_type="Wilaya",
                   code="23"),
    ])
    assert len(props) == 1
    assert props[0].verdict == "arbitrage"


def test_paris_ne_produit_aucune_proposition_de_fusion():
    """D3 — une paire dont les codes officiels s'opposent n'est pas un doublon.

    Remplace `test_paris_part_en_arbitrage_et_jamais_en_auto`, qui attendait
    une proposition d'arbitrage. Le module a PROUVÉ que le département 75 et la
    commune 75056 sont deux entités réelles distinctes : proposer quand même
    leur fusion à un humain, dans un fichier qu'une commande irréversible
    exécute après relecture, c'est offrir un bouton pour détruire ce que
    l'algorithme vient d'établir. Ce n'est pas un doublon à trancher, c'est une
    non-fusion établie — donc rien à proposer.

    Le cas reste celui qui doit devenir rouge si le veto disparaît : sans lui,
    la paire réapparaît (et le YAML de fusion la propose).
    """
    props = etager_lieux([
        PlaceFacts(gramps_id="P0301", handle="HA", nom="Paris", place_type="Department",
                   code="75", lat="48.8589", long="2.347"),
        PlaceFacts(gramps_id="P0008", handle="HB", nom="Paris", place_type="Municipality",
                   code="75056", lat="48.8589", long="2.347"),
    ])
    assert props == []


def test_grappe_de_trois_produit_deux_propositions_sur_le_meme_survivant():
    """Verrens-Arvey : l'égalité de nom est transitive, une seule passe suffit."""
    props = etager_lieux([
        _commune("P0178", "Verrens-Arvey", code="73312", lat="45.6", long="6.4", retroliens=4),
        _commune("P0192", "Verrens-Arvey", code="73312", lat="45.6", long="6.4", retroliens=19),
        _commune("P0198", "Verrens-Arvey", code="73312", lat="45.6", long="6.4", retroliens=5),
    ])
    assert len(props) == 2
    assert {p.gramps_id_keep for p in props} == {"P0192"}
    assert {p.gramps_id_merge for p in props} == {"P0178", "P0198"}
    assert all(p.verdict == "auto" for p in props)


def test_la_perte_evitee_est_rapportee():
    props = etager_lieux([
        _commune("P0387", "Apremont-la-Forêt", retroliens=50),
        _commune("P0148", "Apremont-la-Forêt", code="55012", lat="48.8", long="5.6",
                 retroliens=1),
    ])
    assert props[0].gramps_id_keep == "P0148"
    assert "coordonnées" in props[0].perte_evitee


def test_lieu_sans_nom_est_ignore():
    props = etager_lieux([
        _commune("P1", "", code="18044"),
        _commune("P2", "", code="18044"),
    ])
    assert props == []


def test_etage_lieux_liste_vide_ne_produit_rien():
    assert etager_lieux([]) == []


def test_etage_lieux_regroupe_les_variantes_de_casse_et_d_accents():
    """Le regroupement se fait sur le nom NORMALISÉ : deux orthographes de la
    même commune (casse, séparateurs) doivent finir dans le même groupe, pas
    seulement `normaliser_nom_lieu` en isolation."""
    props = etager_lieux([
        _commune("P1", "Saint-Palais", code="18205"),
        _commune("P2", "SAINT PALAIS", code="18205"),
    ])
    assert len(props) == 1
    assert props[0].gramps_id_keep == "P1"
    assert props[0].canonical == "Saint-Palais"


def test_etage_lieux_canonical_est_le_nom_exact_du_survivant():
    """`canonical` doit reprendre l'orthographe RÉELLE du survivant choisi par
    richesse, pas une casse arbitraire ni la clé normalisée."""
    props = etager_lieux([
        _commune("P9", "cerbois", code="18044"),
        _commune("P1", "Cerbois", code="18044", lat="47.1", long="2.3"),
    ])
    assert props[0].gramps_id_keep == "P1"
    assert props[0].canonical == "Cerbois"


def test_etage_lieux_reason_arbitrage_mentionne_la_relecture_humaine():
    props = etager_lieux([
        PlaceFacts(gramps_id="P0343", handle="HA", nom="Annaba", place_type="Department"),
        PlaceFacts(gramps_id="P0383", handle="HB", nom="Annaba", place_type="Wilaya",
                   code="23"),
    ])
    assert "relecture humaine" in props[0].reason


def test_etage_lieux_verdicts_mixtes_dans_une_meme_grappe():
    """Un survivant peut prouver sa fusion avec un absorbé (code commun) tout en
    n'en prouvant aucune avec un autre — les deux propositions du même groupe
    portent alors des verdicts différents. Rien dans le brief ne verrouillait ce
    mélange (la grappe de trois testée n'exerçait que le cas 'tout auto').

    L'absence de preuve pour C vient ici de son TYPE (Department contre
    Municipality, sans code pour trancher), et non plus d'un code officiel
    différent : depuis la propagation du veto à la grappe, un code distinct
    disqualifierait le groupe entier et le mélange de verdicts serait
    impossible — c'est précisément ce que verrouille
    `test_un_veto_entre_deux_absorbes_bloque_toute_la_grappe`. Le mélange
    lui-même reste réel, et c'est lui que ce test protège.
    """
    props = etager_lieux([
        _commune("S", "Groupe", code="18044", lat="47.1", long="2.3", retroliens=100),
        _commune("B", "Groupe", code="18044", retroliens=5),
        _commune("C", "Groupe", place_type="Department", retroliens=1),
    ])
    assert len(props) == 2
    verdicts = {p.gramps_id_merge: p.verdict for p in props}
    assert verdicts == {"B": "auto", "C": "arbitrage"}


def test_une_fusion_auto_ne_detruit_jamais_un_attribut_du_lieu_absorbe():
    """C1 — le survivant peut être choisi SANS code face à un absorbé qui en porte un.

    Deux « Cerbois » de richesse égale (2 chacun) : P1 porte coordonnées +
    rattachement, P2 coordonnées + le code officiel 18044. La richesse ne
    départage pas, les rétroliens si — 99 contre 1 — et P1 survit. Les types
    sont égaux et les coordonnées identiques, donc la voie des coordonnées
    conclut : verdict automatique, irréversible, que personne ne relit. Le
    18044 — « l'identifiant canonique » de la docstring du module, ce qui fonde
    toute la force de la preuve — serait écrasé, et le rapport annoncerait la
    perte ÉVITÉE (« rattachement ») sans jamais nommer la perte SUBIE.

    Une fusion automatique ne doit rien détruire : dès que l'absorbé porte un
    attribut absent du survivant, c'est à un humain de trancher, et le motif
    doit nommer ce qui disparaîtrait.
    """
    props = etager_lieux([
        _commune("P1", "Cerbois", lat="47.1", long="2.3", a_parent=True, retroliens=99),
        _commune("P2", "Cerbois", lat="47.1", long="2.3", code="18044", retroliens=1),
    ])
    assert len(props) == 1
    p = props[0]
    assert (p.gramps_id_keep, p.gramps_id_merge) == ("P1", "P2")
    # Le champ `perte_evitee` était « rattachement » tant que la garde surveillait
    # cet attribut. Il ne le surveille plus (la fusion Gramps unionne les listes,
    # le rattachement survit) et P1 ne porte, parmi les champs réellement écrasés,
    # rien que P2 n'ait : le rapport n'a donc aucune perte évitée à annoncer. Le
    # cœur du test — un survivant SANS code face à un absorbé qui en porte un, et
    # la fusion automatique refusée pour cela — est inchangé.
    assert p.perte_evitee == ""
    assert p.verdict == "arbitrage"
    assert "perte" in p.reason and "code" in p.reason
    assert "relecture humaine" in p.reason


def test_une_fusion_auto_ne_detruit_jamais_le_type_du_lieu_absorbe():
    """D1 — le seul enregistrement TYPÉ de la grappe ne doit pas disparaître en silence.

    Deux « Vierzon » du même code officiel 18279, mêmes coordonnées, tous deux
    rattachés : la preuve canonique conclut. Mais P1, le survivant (80
    rétroliens contre 3), n'a pas de type, et P2 en a un. `place_type` est un
    champ SIMPLE — la fusion Gramps ne garde que ceux du survivant — donc la
    fusion automatique effacerait « Municipality » sans que personne ne le
    relise ni ne le sache.

    C'est doublement grave : `evaluer_preuve` fait dépendre sa voie des
    coordonnées de DEUX types connus et égaux. Fusionner ainsi dégrade la
    capacité du module à prouver au tour suivant. Et l'absence de type est
    l'état majoritaire de l'arbre réel : le montage est courant, pas exotique.
    """
    props = etager_lieux([
        _commune("P1", "Vierzon", place_type="", code="18279", lat="47.22",
                 long="2.07", a_parent=True, retroliens=80),
        _commune("P2", "Vierzon", place_type="Municipality", code="18279",
                 lat="47.22", long="2.07", a_parent=True, retroliens=3),
    ])
    assert len(props) == 1
    p = props[0]
    assert (p.gramps_id_keep, p.gramps_id_merge) == ("P1", "P2")
    assert p.verdict == "arbitrage"
    assert "type" in p.reason
    assert "relecture humaine" in p.reason


def test_le_veto_de_grappe_epargne_les_paires_prouvees_par_un_code_identique():
    """D2 — un code officiel est canonique : un veto ailleurs ne l'affaiblit pas.

    Quatre « Saint-Palais » : deux portant 18205 (le Cher) et deux portant 17398
    (la Charente-Maritime). La grappe est bel et bien vetoée — elle mélange deux
    entités réelles — mais que 17398 existe à côté ne fragilise en RIEN la preuve
    que les deux 18205 sont le même lieu. Dégrader cette fusion-là en relecture
    vidait la commande de son intérêt : sur les grappes à deux entités, 92 % des
    paires dégradées par le veto de grappe étaient prouvées par un code identique.

    Le veto ne doit donc mordre que sur les preuves NON canoniques (coordonnées).
    Les deux paires 18205/17398 qui touchent le survivant, elles, ne sont plus
    proposées du tout (D3).
    """
    props = etager_lieux([
        _commune("P0205", "Saint-Palais", code="18205", lat="47.2", long="2.1",
                 retroliens=30),
        _commune("P0206", "Saint-Palais", code="18205", lat="47.2", long="2.1",
                 retroliens=12),
        _commune("P0398", "Saint-Palais", code="17398", lat="45.6", long="-0.4",
                 retroliens=8),
        _commune("P0399", "Saint-Palais", code="17398", lat="45.6", long="-0.4",
                 retroliens=4),
    ])
    assert {p.gramps_id_merge: p.verdict for p in props} == {"P0206": "auto"}
    assert props[0].reason == "homonymes — code officiel identique"


def test_le_veto_de_grappe_mord_toujours_sur_une_preuve_par_coordonnees():
    """D2, la borne haute : la permissivité s'arrête au code officiel.

    Miroir exact du test précédent, un seul changement — le membre qui prouve ne
    porte AUCUN code et conclut par la position (P0206 : mêmes type et
    coordonnées que le survivant). Une preuve par coordonnées n'est pas
    canonique : elle repose sur une égalité de position que deux entités
    voisines peuvent partager, et c'est exactement ce que le veto de grappe
    protège. Sans ce test, une correction plus permissive — épargner toute paire
    prouvée, quelle que soit la voie — serait indiscernable de celle qui est
    livrée.
    """
    props = etager_lieux([
        _commune("P0205", "Saint-Palais", code="18205", lat="47.2", long="2.1",
                 retroliens=30),
        _commune("P0206", "Saint-Palais", lat="47.2", long="2.1", retroliens=12),
        _commune("P0398", "Saint-Palais", code="17398", lat="45.6", long="-0.4",
                 retroliens=8),
        _commune("P0399", "Saint-Palais", code="17398", lat="45.6", long="-0.4",
                 retroliens=4),
    ])
    contamine = next(p for p in props if p.gramps_id_merge == "P0206")
    assert contamine.verdict == "arbitrage"
    assert "grappe" in contamine.reason


def test_un_veto_entre_deux_absorbes_bloque_toute_la_grappe():
    """C2 — la preuve n'était évaluée qu'entre le survivant et chaque absorbé.

    Trois « Bourges » aux mêmes coordonnées : P0010 (code 18033, 40 rétroliens),
    P0011 (code 18034, 39 rétroliens) et P0012 (sans code, 5 rétroliens). Le
    couple P0010/P0011 est vetoé — deux codes officiels distincts, donc deux
    entités réelles. Mais P0012, comparé au seul survivant, prouvait par
    coordonnées et partait en fusion automatique irréversible ; et il suffirait
    que P0011 passe à 41 rétroliens pour qu'il soit absorbé dans l'AUTRE entité.
    Un rattachement irréversible ne peut pas basculer sur un compte de
    rétroliens quand l'algorithme a lui-même établi que la grappe mélange deux
    entités distinctes : le veto se propage à tout le groupe.
    """
    props = etager_lieux([
        _commune("P0010", "Bourges", code="18033", lat="47.08", long="2.39", retroliens=40),
        _commune("P0011", "Bourges", code="18034", lat="47.08", long="2.39", retroliens=39),
        _commune("P0012", "Bourges", lat="47.08", long="2.39", retroliens=5),
    ])
    # La paire vetoée elle-même (P0010/P0011) n'est plus proposée du tout : ce
    # n'est pas un doublon à trancher mais une non-fusion établie (D3). Le test
    # comptait 2 propositions quand elle en faisait partie ; seul P0012, le
    # membre réellement contaminé, subsiste — et c'est lui que ce test protège.
    assert {p.gramps_id_merge for p in props} == {"P0012"}
    assert {p.gramps_id_keep for p in props} == {"P0010"}
    assert all(p.verdict == "arbitrage" for p in props)
    contamine = props[0]
    assert "grappe" in contamine.reason
    assert "relecture humaine" in contamine.reason


def test_un_veto_qui_n_implique_pas_le_survivant_bloque_quand_meme_la_grappe():
    """C2, cas strict : la paire vetoée ne touche PAS le survivant.

    Dans le scénario ci-dessus, le survivant est lui-même membre de la paire
    vetoée — un balayage qui ne comparerait que « survivant contre chaque
    autre » y suffirait encore. Ici non : le survivant P0001 n'a aucun code, donc
    il n'oppose de veto à personne ; le veto est entièrement contenu entre deux
    ABSORBÉS, P0010 (18033) et P0011 (18034). C'est le trou exact que la lecture
    par paires du survivant laisse ouvert, et P0012 — sans code, coordonnées et
    rattachement identiques à ceux du survivant, donc sans perte à signaler —
    est le membre qui passerait en fusion automatique irréversible.

    Les quatre lieux ont une richesse de 2, si bien que ce sont les rétroliens
    qui désignent P0001 : le survivant est délibérément le seul à ne rien porter
    qui puisse déclencher la garde C1.
    """
    props = etager_lieux([
        _commune("P0001", "Bourges", lat="47.08", long="2.39", a_parent=True, retroliens=50),
        _commune("P0010", "Bourges", code="18033", lat="47.08", long="2.39", retroliens=10),
        _commune("P0011", "Bourges", code="18034", lat="47.08", long="2.39", retroliens=9),
        _commune("P0012", "Bourges", lat="47.08", long="2.39", a_parent=True, retroliens=5),
    ])
    assert len(props) == 3
    assert {p.gramps_id_keep for p in props} == {"P0001"}
    contamine = next(p for p in props if p.gramps_id_merge == "P0012")
    assert contamine.perte_evitee == ""            # rien ne distingue ces deux-là
    assert contamine.verdict == "arbitrage"
    assert "grappe" in contamine.reason
    assert all(p.verdict == "arbitrage" for p in props)


def test_une_grappe_saine_fusionne_toujours_automatiquement():
    """La porte reste ouverte : ni veto ni perte, donc les trois fusionnent seules.

    Garde-fou contre un durcissement excessif des deux corrections ci-dessus —
    trois lieux du même code officiel, tous également renseignés : rien à
    détruire, aucune paire vetoée, la fusion automatique reste légitime.
    """
    props = etager_lieux([
        _commune("P0178", "Verrens-Arvey", code="73312", lat="45.6", long="6.4",
                 a_parent=True, retroliens=4),
        _commune("P0192", "Verrens-Arvey", code="73312", lat="45.6", long="6.4",
                 a_parent=True, retroliens=19),
        _commune("P0198", "Verrens-Arvey", code="73312", lat="45.6", long="6.4",
                 a_parent=True, retroliens=5),
    ])
    assert len(props) == 2
    assert all(p.verdict == "auto" for p in props)
    assert all(p.reason == "homonymes — code officiel identique" for p in props)


def test_une_fusion_auto_ne_detruit_jamais_des_coordonnees_concurrentes():
    """C1, scénario 1 — deux « Bourges » du même code, deux géocodages.

    P0001 porte des coordonnées grossières et 90 rétroliens, P0002 des
    coordonnées précises et 3. Richesse égale, les rétroliens désignent P0001, et
    la preuve par code officiel conclut : fusion automatique, irréversible, que
    personne ne relit — et les coordonnées précises sont DÉTRUITES, la perte
    rapportée restant vide. La garde ne comparait que présence contre absence.
    """
    props = etager_lieux([
        _commune("P0001", "Bourges", code="18033", lat="47.1", long="2.4",
                 retroliens=90),
        _commune("P0002", "Bourges", code="18033", lat="47.0810", long="2.3988",
                 retroliens=3),
    ])
    assert len(props) == 1
    p = props[0]
    assert (p.gramps_id_keep, p.gramps_id_merge) == ("P0001", "P0002")
    assert p.verdict == "arbitrage"
    assert "coordonnées" in p.reason
    assert "relecture humaine" in p.reason


def test_une_fusion_auto_ne_detruit_jamais_un_type_concurrent():
    """C1, scénario 2 — deux « Cerbois » du même code, deux types CONNUS.

    Le module refuse d'INFÉRER entre `Municipality` et `City` — c'est la garde
    qui protège Paris — mais acceptait d'en DÉTRUIRE un sur la voie du code :
    P0070, seul porteur du type `City`, disparaissait sans que sa valeur
    concurrente soit seulement nommée.
    """
    props = etager_lieux([
        _commune("P0064", "Cerbois", code="18044", lat="47.1", long="2.3",
                 place_type="Municipality", retroliens=90),
        _commune("P0070", "Cerbois", code="18044", lat="47.1", long="2.3",
                 place_type="City", retroliens=3),
    ])
    assert len(props) == 1
    p = props[0]
    assert (p.gramps_id_keep, p.gramps_id_merge) == ("P0064", "P0070")
    assert p.verdict == "arbitrage"
    assert "type" in p.reason
    assert "relecture humaine" in p.reason


def test_le_rattachement_ne_designe_plus_le_survivant():
    """C1, scénario 3 — l'attribut qui ne risque rien tranchait le choix du survivant.

    P0001 est rattaché, géocodé grossièrement, et porte 2 rétroliens ; P0002
    n'est pas rattaché, porte des coordonnées précises et 500 rétroliens. En
    comptant le rattachement, la richesse donnait 2 contre 1 et P0001 survivait :
    500 rétroliens contre 2, et c'est le rattachement — unionné par la fusion,
    donc jamais détruit — qui tranchait.
    """
    props = etager_lieux([
        _commune("P0001", "Vierzon", code="18279", lat="47.2", long="2.1",
                 a_parent=True, retroliens=2),
        _commune("P0002", "Vierzon", code="18279", lat="47.2231", long="2.0686",
                 retroliens=500),
    ])
    assert len(props) == 1
    assert props[0].gramps_id_keep == "P0002"


def test_deux_entites_sans_code_sous_deux_contenants_partent_en_arbitrage():
    """C2, bout en bout — deux « Saint-Michel » de deux départements.

    Mêmes type et coordonnées, aucun code officiel pour opposer un veto : la voie
    des coordonnées concluait à la fusion automatique. Les contenants, eux,
    diffèrent — et c'est le discriminant que le modèle de faits avait effacé.
    """
    props = etager_lieux([
        _commune("P0100", "Saint-Michel", lat="47.1", long="2.3",
                 parent_id="HD18", retroliens=20),
        _commune("P0200", "Saint-Michel", lat="47.1", long="2.3",
                 parent_id="HD37", retroliens=4),
    ])
    assert len(props) == 1
    p = props[0]
    assert p.verdict == "arbitrage"
    assert "aucune preuve" in p.reason
    assert "relecture humaine" in p.reason


def test_etage_lieux_ordonne_les_groupes_par_nom_normalise():
    """Deux groupes indépendants doivent sortir dans un ordre déterministe
    (alphabétique sur la clé normalisée), pas dans l'ordre d'arrivée des lieux."""
    props = etager_lieux([
        _commune("P1", "Vierzon", code="18279"),
        _commune("P2", "Vierzon", code="18279"),
        _commune("P3", "Bourges", code="18033"),
        _commune("P4", "Bourges", code="18033"),
    ])
    assert [p.canonical for p in props] == ["Bourges", "Vierzon"]
