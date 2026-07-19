"""Matching against the Mémoire des hommes military-death gazetteer (local SQLite).

The user builds `militaires.sqlite` from the official open data downloads (2M rows,
table `deces_militaires`); this module queries it offline — zero quota, zero LLM.
The proof of a match is the official ark permalink to the scanned fiche.
"""

from __future__ import annotations

import os
import sqlite3
import unicodedata
from pathlib import Path

from crewai_custom_tools.tools.genealogy.analysis.identity import score_identity

DEFAULT_DB = "data/fr-militaires/normalise/militaires.sqlite"

_COLS = ("base", "nom", "prenom", "naissance_date", "naissance_lieu",
         "naissance_departement", "naissance_pays", "deces_date", "deces_lieu",
         "deces_pays", "unite", "reference", "lien_ark")


def db_path() -> Path:
    return Path(os.environ.get("GENECREW_MILITAIRES_DB", DEFAULT_DB))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def query_militaires(surname: str, *, db: Path | None = None,
                     limit: int = 2000) -> list[dict]:
    """All register rows whose normalized surname matches. Offline.

    The limit is a safety net, not a page: common surnames have hundreds of rows and
    an arbitrary LIMIT 50 silently dropped the right one (real case: Léon Clavier,
    row ~150 of 200, exact birth match missed).
    """
    path = db or db_path()
    if not Path(path).exists():
        raise FileNotFoundError(
            f"gazetteer militaire absent: {path} — lancer l'ETL Mémoire des hommes")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            f"SELECT {', '.join(_COLS)} FROM deces_militaires "
            "WHERE nom_normalise = ? LIMIT ?", (_norm(surname), limit)).fetchall()
    finally:
        con.close()
    return [dict(zip(_COLS, r)) for r in rows]


def score_militaire(surname: str, given: str, birth_iso: str, row: dict) -> float:
    """Identity score of one register row (shared rule: year alone never suffices)."""
    return score_identity(surname, given, birth_iso,
                          row.get("nom", ""),
                          (row.get("prenom") or "").replace(",", " ").split(),
                          row.get("naissance_date", ""))


def match_militaires(surname: str, given: str, birth_iso: str, *,
                     db: Path | None = None) -> list[tuple[dict, float]]:
    """Scored candidate rows, best first, zero-scores dropped. Offline."""
    scored = [(row, score_militaire(surname, given, birth_iso, row))
              for row in query_militaires(surname, db=db)]
    scored = [(r, s) for r, s in scored if s > 0.0]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored
