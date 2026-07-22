"""Détection des doublons de lieux : candidats, preuve, survivant. Pur, sans réseau.

Pendant de `duplicates.py`, qui fait le même travail pour les personnes, avec une
différence décisive : une commune possède un **identifiant canonique** — son code
officiel — que les personnes n'ont pas. La preuve y est donc plus forte et plus
simple à énoncer. La doctrine, elle, ne change pas : la ressemblance ne prouve
jamais l'identité (ADR 0013).

**Écart assumé sur les codes NUS.** Le moteur d'import de relevés du dépôt
applicatif voisin (`genecrew/src/genecrew/releves.py`, `_identifiant_resolu` et
`_comparer_lieux`) pose la garde inverse : une valeur sans préfixe pays y est
IGNORÉE, « un code INSEE français `18209` et un numéro OFS suisse `18209` sont
deux chaînes ÉGALES sans être la même commune ». Ce module-ci, lui, tient
l'égalité de deux codes NUS pour une preuve canonique, suffisante à une fusion
automatique et exemptée du veto de grappe. C'est un écart délibéré, pas un
oubli :

  - les entrées ne sont pas les mêmes. Le moteur de relevés joint l'arbre à un
    référentiel EXTERNE, résolu pays par pays, où la même chaîne peut venir de
    deux référentiels nationaux. Ici, les deux codes sortent du MÊME arbre, du
    même champ `code`, saisi par la même personne — et ils y sont nus : imposer
    le contrat de préfixe ne rendrait pas le module plus strict, il le
    désarmerait entièrement (plus aucune preuve, donc plus aucune fusion) ;
  - une précondition que le moteur de relevés n'a pas filtre déjà : deux lieux
    ne sont comparés que s'ils partagent le NOM normalisé (`etager_lieux` groupe
    sur l'égalité). Il faudrait donc une commune française et une commune suisse
    à la fois homonymes ET de même code nu dans le même arbre.

Ce qui rendrait l'écart dangereux, et qu'il faut surveiller : (1) un groupement
par ressemblance de noms au lieu de l'égalité — la précondition ci-dessus
tomberait ; (2) le chantier référentiel écrivant dans `code` les codes de
plusieurs pays (les résolveurs `geo/` sont routés par pays) — deux codes égaux
par accident ne se contenteraient pas de ne pas opposer de veto, ils
PROUVERAIENT une fusion automatique. Le correctif, ce jour-là, est de préfixer
le code par le pays à la collecte (`"FR:18033"`) : la comparaison n'existe qu'à
un seul endroit, `_oppose_un_veto`, dont `evaluer_preuve` dépend.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from itertools import combinations

from crewai_custom_tools.tools.genealogy.models.domain import (
    PlaceFacts, PlaceMergeProposition,
)

__all__ = [
    "choisir_survivant", "etager_lieux", "evaluer_preuve",
    "normaliser_nom_lieu", "perte_evitee", "richesse",
]

# Les ligatures ne sont pas des accents : NFD ne les décompose pas. « Vœuil-et-Giget »
# et « Voeuil-et-Giget » désignent pourtant la même commune de Charente. Cette table
# se limite aux ligatures ; les lettres barrées (ø/Ø danois, ł polonais, đ croate…)
# n'en sont pas — ce sont des lettres à part entière, distinctes d'un accent ou d'une
# ligature composée — et restent délibérément hors champ.
_LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})

# L'apostrophe typographique ’ (U+2019) est l'usage standard et arrive par
# copier-coller ; elle rejoint la classe des séparateurs plutôt que d'être
# supprimée — sinon « L'Isle-Adam » se confondrait avec « Lisle-Adam ».
_SEPARATEURS = re.compile(r"[\s\-'’]+")


def normaliser_nom_lieu(nom: str) -> str:
    """Nom de lieu → clé de comparaison : sans accents, minuscule, séparateurs unifiés."""
    deplie = (nom or "").translate(_LIGATURES)
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", deplie)
        if unicodedata.category(c) != "Mn")
    return _SEPARATEURS.sub(" ", sans_accents).strip().lower()


PREUVE_CODE = "code"
PREUVE_COORDONNEES = "coordonnees"

# L'ignorance a deux orthographes. Le modèle `PlaceFacts` laisse `place_type` à
# `""` par défaut, tandis que l'API Gramps rend le libellé `"Unknown"` — cf.
# `genecrew/places_apply.py`, qui teste `(place.get("place_type") or "Unknown")
# != "Unknown"`. Les deux désignent le même état : on ne sait pas, et faire
# dépendre un verdict de fusion de l'orthographe rendue serait un pur hasard.
# Seule `"unknown"` figure ici : `_type_connu` rend déjà `""` pour un type vide ou
# blanc, si bien que la chaîne vide n'y jouerait aucun rôle. Cette table ne sert
# qu'à ramener l'orthographe de l'API au même état que celle du modèle.
_TYPES_INCONNUS = frozenset({"unknown"})


def _renseigne(champ: str) -> str:
    """Champ libre de l'API → sa valeur utile, ou `""` s'il ne porte que des blancs.

    `code`, `lat` et `long` sont des chaînes saisies à la main dans Gramps. Un
    champ « vidé » en y tapant une espace reste truthy en Python : sans ce
    nettoyage, deux `" "` se prouveraient mutuellement comme un code canonique.
    """
    return (champ or "").strip()


def _type_connu(place: PlaceFacts) -> str:
    """Type du lieu s'il est connu, sinon `""` — l'ignorance n'est pas une valeur."""
    brut = _renseigne(place.place_type)
    return "" if brut.casefold() in _TYPES_INCONNUS else brut


def _oppose_un_veto(a: PlaceFacts, b: PlaceFacts) -> bool:
    """Deux codes officiels renseignés et différents : la preuve de deux entités. Pur.

    Source unique du veto : `evaluer_preuve` appelle ce prédicat plutôt que de
    recopier sa condition. Les deux lectures ont d'abord coexisté, à deux lignes
    identiques près ; elles divergeraient le jour où les codes seraient
    normalisés (préfixe pays, voir la note en tête de module), et l'effet serait
    pire qu'un désaccord — une paire dont les codes ne s'écriraient plus pareil
    déclencherait le veto et disparaîtrait entièrement du lot, rendant un vrai
    doublon invisible jusqu'en relecture.

    `evaluer_preuve` connaît donc ce veto mais ne le distingue pas dans ce
    qu'elle rend : la chaîne vide y confond « rien ne prouve » et « quelque
    chose interdit ». Or les deux ne se propagent pas pareil — une absence de
    preuve ne concerne que la paire, un veto disqualifie tout le groupe.
    """
    code_a, code_b = _renseigne(a.code), _renseigne(b.code)
    return bool(code_a and code_b and code_a != code_b)


def evaluer_preuve(a: PlaceFacts, b: PlaceFacts) -> str:
    """La preuve qui autorise une fusion automatique, ou la chaîne vide. Pur.

    Un VETO passe avant tout — `_oppose_un_veto`, source unique de la règle :
    deux codes RENSEIGNÉS et différents interdisent la fusion, quels que soient
    les types et les coordonnées. C'est lui qui protège Paris — le département 75
    et la commune 75056 sont deux entités réelles. « Renseigné » s'entend après
    nettoyage des blancs : un code ne contenant que des espaces vaut un code
    absent, n'oppose donc aucun veto, et laisse le verdict aux voies ci-dessous.

    Hors veto, deux voies :
      - codes identiques et non vides : un code officiel est canonique, il prouve
        quel que soit le type des deux lieux et quels que soient leurs
        contenants — une même commune peut être rattachée au département dans un
        enregistrement et à l'arrondissement dans l'autre ;
      - deux types CONNUS et égaux, contenants non contradictoires, ET
        coordonnées complètes identiques : la voie des lieux sans code. Les
        coordonnées ne prouvent JAMAIS rien entre types différents — un
        département géocodé reçoit le point de sa préfecture, c'est-à-dire celui
        de sa commune-chef-lieu — ni dès qu'un seul des deux types est inconnu :
        un inconnu n'est jamais égal à un autre inconnu. C'est la doctrine du
        module jumeau `duplicates.py`, qui exige un nom « identique et non vide »
        et refuse dès qu'un parent est inconnu. Sans elle, un arrondissement
        « Bourges » encore `Unknown` mais géocodé au point de son chef-lieu
        fusionnerait tout seul avec la commune du même nom — l'état sans type
        étant l'état majoritaire de l'arbre réel.

    Le refus par CONTENANT est à la voie des coordonnées ce que le veto des codes
    est à tout le verdict : deux contenants connus et différents désignent deux
    entités, pas deux saisies d'une même. C'est le seul discriminant des
    homonymes sans code officiel — deux « Saint-Michel » aux coordonnées
    identiques (un géocodage approximatif ou un copier-coller suffit à le
    produire) mais rattachées à deux départements. Un contenant inconnu ne
    refuse rien : l'ignorance n'est pas une différence, et un refus sur une
    non-mesure écarterait de vrais doublons d'un arbre où le rattachement manque
    souvent. Ce refus reste LOCAL à la paire, il ne se propage pas à la grappe
    comme le veto des codes : le rattachement est une donnée de saisie révisable,
    pas un identifiant canonique.

    Fonction symétrique : `evaluer_preuve(a, b) == evaluer_preuve(b, a)`. Une
    écriture irréversible ne doit pas dépendre de l'ordre de parcours.
    """
    if _oppose_un_veto(a, b):
        return ""
    if _renseigne(a.code) and _renseigne(b.code):
        return PREUVE_CODE                       # égaux : le veto a écarté l'autre cas
    type_a, type_b = _type_connu(a), _type_connu(b)
    if not type_a or not type_b or type_a != type_b:
        return ""
    parent_a, parent_b = _renseigne(a.parent_id), _renseigne(b.parent_id)
    if parent_a and parent_b and parent_a != parent_b:
        return ""
    coord_a = (_renseigne(a.lat), _renseigne(a.long))
    if all(coord_a) and coord_a == (_renseigne(b.lat), _renseigne(b.long)):
        return PREUVE_COORDONNEES
    return ""


def richesse(p: PlaceFacts) -> int:
    """Nombre d'attributs renseignés parmi coordonnées et code (0 à 2). Pur.

    La liste est calquée sur celle de `perte_evitee` : ce qui départage deux
    candidats au rôle de survivant, ce sont les champs que la fusion ÉCRASE. Le
    rattachement n'en fait pas partie — c'est une liste de références, unionnée
    par la fusion, donc jamais détruite. Le compter faisait trancher le choix par
    le seul attribut qui ne risque rien, contre ceux qui risquent tout : un lieu
    rattaché aux coordonnées grossières et à 2 rétroliens l'emportait sur un lieu
    non rattaché, précis, à 500 rétroliens.

    Le TYPE est écrasé lui aussi mais reste hors de ce compte : `perte_evitee`
    le surveille et dégrade la fusion en arbitrage dès qu'il diverge, ce qui le
    protège sans déplacer de survivant. L'ajouter ici modifierait le survivant
    de grappes que rien n'oblige à changer, alors que le compte sert seulement à
    ne pas garder la coquille la plus vide.
    """
    return sum((
        bool(_renseigne(p.lat) and _renseigne(p.long)),
        bool(_renseigne(p.code)),
    ))


def choisir_survivant(lieux: list[PlaceFacts]) -> PlaceFacts:
    """Le lieu qui survit à la fusion du groupe. Pur.

    Richesse d'abord, rétroliens ensuite, identifiant le plus petit en dernier
    recours — la règle doit être TOTALE pour que deux exécutions donnent le même
    résultat sur des données identiques.

    L'ordre n'est pas un confort : la fusion Gramps unionne les listes mais les
    champs simples restent ceux du survivant. Garder une coquille vide contre un
    lieu renseigné effacerait définitivement ses coordonnées et son code.
    """
    return min(lieux, key=lambda p: (-richesse(p), -p.retroliens, p.gramps_id))


def perte_evitee(conserve: PlaceFacts, ecarte: PlaceFacts) -> str:
    """Les champs simples que la fusion effacerait en gardant `conserve`. Pur.

    Les deux paramètres sont NEUTRES à dessein : la fonction est appelée dans les
    deux sens, et c'est le sens de l'appel qui décide de ce que la valeur rendue
    signifie. `perte_evitee(survivant, absorbe)` rend la perte SUBIE — ce que la
    fusion va réellement détruire, la garde d'`etager_lieux` ; l'appel miroir
    `perte_evitee(absorbe, survivant)` rend la perte ÉVITÉE — ce qu'on aurait
    détruit en gardant l'autre, le champ du même nom dans le rapport. Nommer les
    paramètres d'après le second appel obligeait chaque site à justifier son
    ordre en plusieurs lignes de commentaire ; l'inversion a égaré deux revues.

    **Les attributs surveillés sont les CHAMPS SIMPLES** — coordonnées, code,
    type — parce que ce sont les seuls que la fusion Gramps écrase : elle unionne
    les listes et ne conserve, pour le reste, que les valeurs du lieu gardé.

    Le **rattachement** à un contenant n'y figure donc pas : c'est une liste de
    références (`placeref_list`), unionnée comme les autres, qui SURVIT à la
    fusion. L'annoncer perdu dégradait en relecture des fusions ne détruisant
    rien, et l'état « rattaché » est massivement répandu dans l'arbre.

    Le **type**, à l'inverse, est un champ simple bel et bien écrasé. Son absence
    de la liste laissait disparaître en silence le seul enregistrement typé d'une
    grappe — et cette perte-là se paie deux fois, puisque `evaluer_preuve` fait
    dépendre sa voie des coordonnées de deux types CONNUS : chaque type effacé
    dégrade la capacité du module à prouver au tour suivant.

    « Perdu » couvre DEUX états, et pas seulement l'absence : le champ n'est pas
    renseigné chez `conserve`, ou il l'est des deux côtés avec des valeurs
    DIFFÉRENTES. Ne compter que le premier faisait détruire en silence les
    coordonnées précises de deux « Bourges » du même code au profit des
    grossières, et le seul enregistrement `City` d'une grappe où le gardé était
    `Municipality` — deux types que `evaluer_preuve` juge pourtant assez
    différents pour interdire toute inférence entre eux.

    Le **code** reste, lui, présence contre absence : deux codes officiels
    concurrents relèvent du VETO, qui retire la paire du lot avant tout calcul de
    perte (`etager_lieux`). Une branche « codes différents » ici serait du code
    mort donnant l'illusion d'une garde.
    """
    perdus = []
    coord_conserve = (_renseigne(conserve.lat), _renseigne(conserve.long))
    coord_ecarte = (_renseigne(ecarte.lat), _renseigne(ecarte.long))
    if all(coord_ecarte) and coord_ecarte != coord_conserve:
        perdus.append("coordonnées")
    if _renseigne(ecarte.code) and not _renseigne(conserve.code):
        perdus.append("code")
    type_conserve, type_ecarte = _type_connu(conserve), _type_connu(ecarte)
    if type_ecarte and type_ecarte != type_conserve:
        perdus.append("type")
    return ", ".join(perdus)


_MOTIFS = {
    PREUVE_CODE: "code officiel identique",
    PREUVE_COORDONNEES: "coordonnées identiques, même type, aucun code",
}


def _grappe_vetoee(membres: list[PlaceFacts]) -> bool:
    """Vrai si UNE paire quelconque du groupe est vetoée — pas seulement avec le survivant.

    La preuve n'était évaluée qu'entre le survivant et chaque absorbé, si bien
    qu'une grappe pouvait porter la preuve qu'elle mélange deux entités réelles
    distinctes et produire quand même des fusions automatiques : le membre sans
    code se rattachait au survivant, et un simple compte de rétroliens de plus
    chez un autre membre l'aurait rattaché à l'entité voisine. Une écriture
    irréversible ne peut pas dépendre de ça.

    **Portée du veto** : il dégrade les preuves NON canoniques du groupe, pas
    toutes. Une paire prouvée par un code officiel identique reste automatique —
    un code est un identifiant canonique, et que deux AUTRES membres de la
    grappe portent des codes différents ne fragilise en rien la preuve que ces
    deux-là sont le même lieu (quatre « Saint-Palais », deux 18205 et deux
    17398 : la fusion des deux 18205 entre eux reste prouvée). Une preuve par
    coordonnées, elle, repose sur une égalité de position que deux entités
    voisines peuvent partager : c'est celle-là que le mélange avéré d'entités
    disqualifie. Voir `etager_lieux`, seul appelant.

    Quadratique, mais sur des homonymes d'un même nom — quelques membres.
    """
    return any(_oppose_un_veto(a, b)
               for a, b in combinations(membres, 2))


def etager_lieux(lieux: list[PlaceFacts]) -> list[PlaceMergeProposition]:
    """Groupe les homonymes, choisit un survivant par groupe, évalue chaque autre. Pur.

    Le groupement se fait sur l'ÉGALITÉ de nom normalisé, qui est une relation
    d'équivalence : les groupes sont donc complets dès la première lecture, et
    fusionner deux lieux n'en renomme aucun autre. C'est ce qui rend inutile la
    boucle de convergence que la déduplication des personnes exige — voir l'écart
    documenté en tête du plan.

    Une preuve ne suffit pas à conclure « auto ». Deux gardes la dégradent en
    relecture humaine, parce qu'une fusion automatique est irréversible et que
    personne ne la relit :

      - **perte réelle** : l'absorbé porte un champ simple que le survivant n'a
        pas. C'est `perte_evitee` appelée dans l'autre sens que pour le rapport —
        (survivant, absorbe) au lieu de (absorbe, survivant) — donc exactement ce
        que la fusion va effacer. Une fusion automatique ne détruit jamais
        d'information ; c'est là qu'un humain doit trancher, et le motif nomme ce
        qui disparaîtrait.
      - **veto de grappe** : voir `_grappe_vetoee`. Le veto ne se lit pas dans le
        verdict de la paire courante, il disqualifie les preuves non canoniques
        du groupe entier — le code officiel, lui, prouve seul et n'en dépend pas.

    Les deux se disent dans le `reason` : le modèle ne gagne aucun champ, le motif
    porte seul l'explication.

    Une paire dont les codes officiels s'opposent ne produit **aucune**
    proposition : le module a prouvé que ces deux lieux sont deux entités
    différentes, ce n'est pas un doublon à trancher mais une non-fusion établie.
    L'inscrire au fichier relu offrirait à un humain pressé un bouton pour
    détruire irréversiblement ce que l'algorithme venait d'établir.
    """
    groupes: dict[str, list[PlaceFacts]] = defaultdict(list)
    for lieu in lieux:
        cle = normaliser_nom_lieu(lieu.nom)
        if cle:                                  # un lieu sans nom exploitable n'est pas candidat
            groupes[cle].append(lieu)

    propositions: list[PlaceMergeProposition] = []
    for _, membres in sorted(groupes.items()):
        if len(membres) < 2:
            continue
        survivant = choisir_survivant(membres)
        vetoee = _grappe_vetoee(membres)
        for absorbe in sorted(membres, key=lambda p: p.gramps_id):
            if absorbe.handle == survivant.handle:
                continue
            if _oppose_un_veto(survivant, absorbe):
                continue                        # non-fusion établie, pas un doublon
            preuve = evaluer_preuve(survivant, absorbe)
            perte_subie = perte_evitee(survivant, absorbe)
            # Le veto de grappe ne mord que sur les preuves non canoniques : un
            # code officiel identique prouve à lui seul, indépendamment de ce que
            # portent les autres membres du groupe.
            degrade_par_grappe = vetoee and preuve != PREUVE_CODE
            auto = bool(preuve) and not perte_subie and not degrade_par_grappe
            motifs = [_MOTIFS[preuve] if preuve else "aucune preuve"]
            if perte_subie:
                motifs.append(f"perte irréversible ({perte_subie})")
            if degrade_par_grappe:
                motifs.append("veto de grappe — codes officiels distincts entre deux membres")
            propositions.append(PlaceMergeProposition(
                gramps_id_keep=survivant.gramps_id, handle_keep=survivant.handle,
                gramps_id_merge=absorbe.gramps_id, handle_merge=absorbe.handle,
                canonical=survivant.nom,
                reason=("homonymes — " + " ; ".join(motifs)
                        + ("" if auto else " : relecture humaine")),
                verdict="auto" if auto else "arbitrage",
                perte_evitee=perte_evitee(absorbe, survivant)))
    return propositions
