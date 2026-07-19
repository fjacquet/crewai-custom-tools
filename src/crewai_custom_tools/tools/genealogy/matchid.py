"""INSEE death-records search via the free MatchID API (deces.matchid.io).

Covers French death records since 1970 — the go-to source to confirm a death
date/place for 20th-century persons in the tree.
"""

import logging

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok

logger = logging.getLogger(__name__)

MATCHID_ENDPOINT = "https://deces.matchid.io/deces/api/v1/search"
USER_AGENT = "crewai-custom-tools/genealogy (research tool)"


def search_deces(last_name: str, first_name: str = "", birth_date: str = "",
                 birth_city: str = "", limit: int = 10) -> list[dict]:
    """Query the MatchID death-records API; return the raw person matches.

    Single HTTP path shared by the CrewAI tool and the deterministic enrichers.
    """
    params: dict = {"lastName": last_name}
    if first_name:
        params["firstName"] = first_name
    if birth_date:
        params["birthDate"] = birth_date
    if birth_city:
        params["birthCity"] = birth_city
    response = requests.get(
        MATCHID_ENDPOINT, params=params,
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
    response.raise_for_status()
    body = (response.json() or {}).get("response") or {}
    return list(body.get("persons") or [])[:limit]


def _birth_concordance(birth_iso: str, match_birth: str) -> float:
    """Concordance of tree birth ('1922-09-29' or '1922') vs INSEE 'YYYYMMDD'. Pure.

    1.0 exact full date, 0.5 same year only, 0.0 mismatch. Year-only concordance is
    deliberately capped so it can NEVER cross the proposal threshold by itself: with a
    27M-record national file, "same common name + same birth year" is a near-certain
    homonym (real alive-person false positives were produced at 0.7).
    """
    tree = birth_iso.replace("-", "").strip()
    insee = (match_birth or "").strip()
    if not tree or not insee:
        return 0.0
    if len(tree) == 8 and len(insee) == 8:
        return 1.0 if tree == insee else (0.5 if tree[:4] == insee[:4] else 0.0)
    return 0.5 if tree[:4] == insee[:4] else 0.0


def score_deces_match(surname: str, given: str, birth_iso: str, match: dict) -> float:
    """Deterministic match score in [0,1] — the score decides, never the LLM. Pure.

    0.5·sim(surname) + 0.2·sim(given vs best first name) + 0.3·birth concordance;
    a divergent birth eliminates (0.0).
    """
    from crewai_custom_tools.tools.genealogy.geo.score import similarity

    name = match.get("name") or {}
    conc = _birth_concordance(birth_iso, ((match.get("birth") or {}).get("date") or ""))
    if conc == 0.0:
        return 0.0
    sim_nom = similarity(surname, name.get("last") or "")
    firsts = name.get("first") or []
    # Tree given names come comma-separated ("Paul, Marcel"); keep the first, clean.
    given_head = (given.replace(",", " ").split() or [""])[0]
    sim_prenom = max((similarity(given_head, f) for f in firsts), default=0.0)
    return round(0.5 * sim_nom + 0.2 * sim_prenom + 0.3 * conc, 3)


def best_deces_match(surname: str, given: str, birth_iso: str,
                     matches: list[dict]) -> tuple[dict, float] | None:
    """Best-scoring raw match with its score; None when no candidate scores > 0. Pure."""
    scored = [(m, score_deces_match(surname, given, birth_iso, m)) for m in matches]
    scored = [(m, s) for m, s in scored if s > 0.0]
    if not scored:
        return None
    return max(scored, key=lambda pair: pair[1])


def _flatten_person(p: dict) -> dict:
    """Flatten one MatchID person record for agent consumption. Pure."""
    name = p.get("name") or {}
    birth, death = p.get("birth") or {}, p.get("death") or {}
    birth_loc, death_loc = birth.get("location") or {}, death.get("location") or {}
    return {
        "score": p.get("score"),
        "nom": name.get("last", ""),
        "prenoms": " ".join(name.get("first") or []),
        "sexe": p.get("sex", ""),
        "naissance_date": birth.get("date", ""),        # YYYYMMDD
        "naissance_lieu": ", ".join(filter(None, [
            birth_loc.get("city", ""), birth_loc.get("country", "")])),
        "deces_date": death.get("date", ""),            # YYYYMMDD
        "deces_lieu": ", ".join(filter(None, [
            death_loc.get("city", ""), death_loc.get("country", "")])),
        "age_au_deces": death.get("age"),
    }


class InseeDecesSearchInput(BaseModel):
    """Input model for the InseeDecesSearchTool."""

    last_name: str = Field(..., description="Surname to search (INSEE death records).")
    first_name: str = Field("", description="First name (improves matching; empty = any).")
    birth_date: str = Field(
        "", description="Birth date or year: YYYY or DD/MM/YYYY or YYYYMMDD (empty = any)."
    )
    birth_city: str = Field("", description="Birth city (empty = any).")
    limit: int = Field(10, description="Max matches returned.")


class InseeDecesSearchTool(BaseTool):
    """Searches the INSEE death records (post-1970) through the MatchID API."""

    name: str = "insee_deces_search"
    description: str = (
        "Searches the French INSEE death records (1970→today) by name, birth date and "
        "birth city, and returns matched persons with death date/place and a match "
        "score. Free API — the standard way to confirm a 20th-century death."
    )
    args_schema: type[BaseModel] = InseeDecesSearchInput

    @api_tool(provider="MatchID", endpoint="DecesSearch", timeout=30.0)
    def _run(self, last_name: str, first_name: str = "",
             birth_date: str = "", birth_city: str = "",
             limit: int = 10) -> str:
        persons = search_deces(last_name, first_name=first_name,
                               birth_date=birth_date, birth_city=birth_city, limit=limit)
        return ok({
            "total": len(persons),
            "matches": [_flatten_person(p) for p in persons],
        })
