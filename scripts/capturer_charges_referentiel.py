"""Capture les charges SPARQL réelles servant de fixtures au référentiel.

À relancer à la main quand les fixtures doivent être rafraîchies. Wikidata bouge : les
fixtures sont figées précisément pour que la suite de tests ne dépende ni du réseau ni de
l'humeur de l'endpoint.

    uv run python scripts/capturer_charges_referentiel.py
"""

import json
import pathlib
import time

from crewai_custom_tools.tools.genealogy.referentiel.config import PAYS_REFERENTIEL
from crewai_custom_tools.tools.genealogy.referentiel.wikidata import build_query
from crewai_custom_tools.tools.web.wikidata import sparql_rows

DESTINATION = pathlib.Path(__file__).parent.parent / "tests" / "fixtures" / "referentiel"
# Quatre pays suffisent : ils portent tous les cas qui ont fait basculer la conception.
# FR = conteneur intermédiaire sans ISO + collision FR-69 ; IT = villes métropolitaines,
# entité sans libellé, Venise ; CH = un sommet portant un code cantonal ; PL = une ville.
PAYS_CAPTURES = ("FR", "IT", "CH", "PL")


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for code in PAYS_CAPTURES:
        pays = PAYS_REFERENTIEL[code]
        rows = sparql_rows(build_query(pays.code_iso, pays.langue, pays.qid), timeout=180.0)
        cible = DESTINATION / f"{code}.json"
        cible.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{code}: {len(rows)} lignes -> {cible}")
        time.sleep(4)


if __name__ == "__main__":
    main()
