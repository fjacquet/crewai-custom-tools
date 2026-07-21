"""Table des pays du référentiel : préfixe ISO, QID Wikidata, types Gramps par niveau.

Ajouter un pays = ajouter une ligne. Les QID ont été vérifiés en ligne le 2026-07-21 ;
ne pas les modifier sans revérifier contre les libellés Wikidata.

Les types sont exclusivement des types Gramps NATIFS : ni `Canton` ni `Wilaya` n'en sont,
et chaque type personnalisé est une ligne de plus à ne pas oublier dans les filtres par
type (cf. la mise en garde TYPES_LIEU_DECES du CLAUDE.md).
"""

from __future__ import annotations

from pydantic import BaseModel


class PaysReferentiel(BaseModel):
    """Un pays du référentiel et la forme de sa hiérarchie administrative."""

    code_iso: str                       # "FR" — préfixe des codes ISO 3166-2
    qid: str                            # "Q142"
    nom: str                            # "France" — le nom du lieu Gramps
    langue: str                         # langue du nom vernaculaire, pour l'appariement
    niveaux: tuple[str, ...]            # types Gramps, du niveau 1 vers le niveau 2


PAYS_REFERENTIEL: dict[str, PaysReferentiel] = {
    "FR": PaysReferentiel(code_iso="FR", qid="Q142", nom="France", langue="fr",
                          niveaux=("Region", "Department")),
    "IT": PaysReferentiel(code_iso="IT", qid="Q38", nom="Italie", langue="it",
                          niveaux=("Region", "Province")),
    "BE": PaysReferentiel(code_iso="BE", qid="Q31", nom="Belgique", langue="nl",
                          niveaux=("Region", "Province")),
    "CH": PaysReferentiel(code_iso="CH", qid="Q39", nom="Suisse", langue="de",
                          niveaux=("State",)),
    "DE": PaysReferentiel(code_iso="DE", qid="Q183", nom="Allemagne", langue="de",
                          niveaux=("State",)),
    "US": PaysReferentiel(code_iso="US", qid="Q30", nom="États-Unis", langue="en",
                          niveaux=("State",)),
    "DZ": PaysReferentiel(code_iso="DZ", qid="Q262", nom="Algérie", langue="ar",
                          niveaux=("Province",)),
    "PL": PaysReferentiel(code_iso="PL", qid="Q36", nom="Pologne", langue="pl",
                          niveaux=("Region",)),
    "SY": PaysReferentiel(code_iso="SY", qid="Q858", nom="Syrie", langue="ar",
                          niveaux=("Province",)),
}
