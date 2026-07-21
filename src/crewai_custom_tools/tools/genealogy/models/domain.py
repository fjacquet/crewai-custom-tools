"""Hand-written domain models for the deterministic audit (Phase 1a).

These are the normalized facts the pure rules operate on — decoupled from the
raw Gramps Web JSON, which the genecrew orchestrator maps into these shapes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field


class EventFact(BaseModel):
    """One dated event, reduced to what the rules need."""

    type: str                       # "Birth", "Death", "Baptism", "Burial", "Marriage"...
    sortval: int = 0                # Julian day number; 0 = unknown/unsortable
    year: int | None = None
    modifier: int = 0               # 0 exact,1 before,2 after,3 about,4 range,5 span,6 text
    quality: int = 0                # 0 normal,1 estimated,2 calculated
    dateval: list = Field(default_factory=list)
    has_citation: bool = False
    place: str = ""                 # hiérarchie complète, depuis profile.<birth|death>.place
    place_name: str = ""            # commune seule, depuis profile.<birth|death>.place_name


class PersonFacts(BaseModel):
    """Normalized person facts for the rules engine."""

    gramps_id: str
    handle: str
    name: str
    surname: str
    given: str
    sex: str                        # "M", "F", "U"
    birth: EventFact | None = None
    death: EventFact | None = None
    events: list[EventFact] = Field(default_factory=list)
    has_any_citation: bool = False
    parent_family_handles: list[str] = Field(default_factory=list)
    family_handles: list[str] = Field(default_factory=list)


class FamilyFacts(BaseModel):
    """Normalized family facts for the family rules (R3, R4, R5)."""

    gramps_id: str
    handle: str
    father_handle: str | None = None
    mother_handle: str | None = None
    child_handles: list[str] = Field(default_factory=list)
    marriage: EventFact | None = None


class Anomaly(BaseModel):
    """One detected inconsistency, attached to a person."""

    rule: str                       # "R1".."R9"
    severity: str                   # "haute" | "moyenne" | "basse"
    gramps_id: str
    handle: str
    message: str                    # human-readable, French
    detail: dict = Field(default_factory=dict)


class DuplicateCandidate(BaseModel):
    """A pair of persons that may be duplicates (R10)."""

    gramps_id_a: str
    gramps_id_b: str
    score: float
    reason: str


class Proposition(BaseModel):
    """One proposal for human review — a FACT change is never written directly."""

    type: str                       # "genre_inconnu" | "genre_contradiction"
    gramps_id: str
    handle: str
    personne: str                   # nom lisible
    champ: str = "gender"
    valeur_actuelle: str            # "U" | "M" | "F"
    valeur_proposee: str            # "M" | "F"
    preuve: str
    confiance: str                  # "haute" | "moyenne"
    priorite: str                   # "haute" | "moyenne"


class ParsedPlace(BaseModel):
    """Result of parsing one flat GEDCOM-style place string (positional, country last)."""

    raw: str
    commune: str = ""
    insee: str | None = None            # 5-char INSEE code if embedded
    ags: str | None = None              # 8-digit Amtlicher Gemeindeschlüssel (Germany)
    postal: str | None = None
    departement: str = ""
    region: str = ""
    country: str = ""                   # normalized country label/ISO
    shifted: bool = False               # positional shift detected (no reliable code)


class PlaceLevel(BaseModel):
    """One node in a place's parent chain (top→down)."""

    name: str
    place_type: str                     # "Country" | "Region" | "Department" | "Municipality"…
    code: str | None = None


class DatedName(BaseModel):
    value: str
    date_qualifier: str | None = None   # None | "avant AAAA-MM-JJ" | "après AAAA-MM-JJ"


class DatedChain(BaseModel):
    """A parent chain valid over a period (top→down)."""

    levels: list[PlaceLevel]
    date_qualifier: str | None = None


class ResolvedPlace(BaseModel):
    """Normalized output every country resolver returns (the resolver contract)."""

    name: str
    place_type: str
    lat: str | None = None              # WGS84 decimal (never Swiss x/y grid)
    long: str | None = None
    code: str | None = None
    chains: list[DatedChain] = Field(default_factory=list)
    alt_names: list[DatedName] = Field(default_factory=list)
    score: float                        # 1.0 authoritative ; <1.0 fuzzy
    ambiguous: bool = False             # ambiguity guard (spec §5) → forces proposition
    source: str
    query: str


class PlaceProposition(BaseModel):
    """One place's standardization proposal (report + YAML)."""

    type: str                           # "lieu_resolu" | "lieu_indecidable"
    gramps_id: str
    handle: str
    original: str
    country: str
    resolution: ResolvedPlace | None = None
    action: str                         # "ecrire" | "proposition" | "indecidable"
    confiance: str                      # "haute" | "moyenne" | "basse"
    priorite: str
    preuve: str


class PlaceMergeProposition(BaseModel):
    """Two existing leaf places resolving to the same canonical place (dedup). Never auto."""

    gramps_id_keep: str
    handle_keep: str
    gramps_id_merge: str
    handle_merge: str
    canonical: str
    reason: str


class PropositionAudit(BaseModel):
    """One precise, human-applicable correction proposal (confidence capped at 2/4).

    Shared vocabulary: emitted by the pure D-rules and by the LLM crew alike.
    """

    type: str = Field(description="date | lieu | relation | nom | source | doublon | autre")
    gramps_id: str
    handle: str
    personne: str
    cible: str = Field(description="Objet Gramps visé (ex. 'événement E0607 de I0010').")
    action: str = Field(description="Le changement exact à appliquer, en une phrase.")
    preuve_url: str = Field(default="", description="URL/référence de la preuve, si preuve.")
    preuve_detail: str = Field(default="", description="Ce que la preuve établit.")
    priorite: str = Field(description="haute | moyenne | basse")
    confiance: int = Field(ge=1, le=2, description="1 plausible, 2 preuve concordante.")


class PropositionsLot(BaseModel):
    """Structured batch of propositions."""

    propositions: list[PropositionAudit] = Field(default_factory=list)


FacteurConcordance = Literal[
    "nom", "prénom", "date complète", "lieu", "unité militaire", "profession",
]
"""Vocabulaire fermé des facteurs de concordance qu'une piste peut invoquer.

Volontairement clos : une source qui voudrait faire valoir « né en 1888 » se
fait refuser par pydantic plutôt que de gonfler son score. L'année seule
n'y figure pas — elle qualifie une date, elle n'en constitue pas une (règle
projet : une année seule n'est jamais discriminante, trop d'homonymes
partagent une naissance la même année).
"""


class Piste(BaseModel):
    """Une piste de recherche : ce qu'une source suggère, jamais ce qu'elle prouve.

    Aucune citation n'est créée à ce stade (document-de-travail §6.3). L'identité
    est celle de la source (ark, id MatchID, Q-item) ; à défaut, une clé dérivée
    des champs identifiants — jamais une URL fabriquée, qui serait un lien mort
    présenté comme preuve.

    `force` est DÉRIVÉ, jamais saisi : voir `Piste.force` ci-dessous. La règle vit
    ici, à côté du modèle, pour que toute source de cette bibliothèque (MatchID
    aujourd'hui, Gallica/Wikidata demain) puisse l'invoquer sans dépendre de
    l'application appelante.
    """

    gramps_id: str
    handle: str
    source: str                       # "matchid" | "mdh" | "gallica" | "wikidata" | …
    identite: str                     # identifiant externe stable, OU clé dérivée
    identite_derivee: bool = False    # True -> la note dira le permalien absent
    url: str | None = None            # None si la source n'en donne pas
    requete: str                      # la requête exacte, rejouable telle quelle
    concordances: list[FacteurConcordance] = Field(default_factory=list)
    divergences: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def force(self) -> Literal["forte", "faible"]:
        """Forte = au moins DEUX facteurs concordants DISTINCTS ET aucune divergence.

        Catégoriel, pas numérique : un score peut valoir 1.0 en masquant une
        ambiguïté (mesuré sur le résolveur de lieux). Dédupliquée : `["nom", "nom"]`
        ne compte que pour un seul facteur — c'est le doublon qui manquait pour que
        cette liste ne se fasse pas passer pour deux concordances indépendantes.

        Non saisissable : `force` n'est plus un paramètre du constructeur. Un appel
        legacy passant `force=...` est silencieusement ignoré par pydantic (champ
        extra sur un `computed_field`) — la valeur ci-dessous reste la seule qui
        compte, y compris à la sérialisation (`model_dump`/`model_dump_json`).
        """
        if self.divergences:
            return "faible"
        return "forte" if len(set(self.concordances)) >= 2 else "faible"


MergeTier = Literal["auto", "arbitrage", "rejet"]
"""Les trois étages de la fusion (spec §4.1).

`auto` : preuve structurelle, fusion sans relecture. `arbitrage` : preuve
partielle, passe par un YAML relu. `rejet` : ressemblance de nom seule — jamais
une preuve.
"""


class MergePair(BaseModel):
    """Une paire de personnes, avec l'étage qui lui a été attribué."""

    gramps_id_a: str
    gramps_id_b: str
    handle_a: str
    handle_b: str
    tier: MergeTier
    regle: str = ""
    """Règle de l'étage auto qui a conclu : `date_complete+parents`,
    `date_complete`, `conjoint+enfant`. Vide pour les étages arbitrage et rejet."""
    blocs: list[str] = Field(default_factory=list)
    """Clés de blocage ayant produit la paire — traçabilité du rappel."""


class MergeCluster(BaseModel):
    """Une grappe de doublons réduite à un seul survivant (spec §4.5)."""

    phoenix_handle: str
    phoenix_gramps_id: str
    titanic_handles: list[str] = Field(default_factory=list)
    titanic_gramps_ids: list[str] = Field(default_factory=list)
    gender_patch: Literal[0, 1] | None = None
    """Genre à écrire sur le phoenix AVANT la fusion, ou None. `Person.merge()`
    ignore le genre : sans ce patch, un phoenix « Inconnu » perdrait sans trace le
    genre connu d'un titanic (spec §2)."""


class Subdivision(BaseModel):
    """Une subdivision administrative résolue depuis Wikidata (référentiel des lieux)."""

    qid: str                            # "Q1273"
    iso: str                            # "CH-VD"
    code: str                           # "VD" — l'ISO amputé du préfixe pays
    libelle_fr: str
    noms: list[str] = []                # noms d'appariement : français, puis vernaculaire
    place_type: str                     # type Gramps NATIF ("State", "Department"…)
    niveau: int                         # 1 = sous le pays, 2 = sous une subdivision de niveau 1
    parent_qid: str                     # QID du pays ou de la subdivision de niveau 1
    lat: str | None = None              # WGS84 décimal
    long: str | None = None
    frwiki: str | None = None           # URL de l'article français


class CollisionIso(BaseModel):
    """Plusieurs entités retenues sous un même code ISO : signalé, jamais écrit."""

    iso: str
    qids: list[str]
    libelles: list[str]
