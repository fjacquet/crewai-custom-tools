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
    first_name: str | None = Field(None, description="First name (improves matching).")
    birth_date: str | None = Field(
        None, description="Birth date or year: YYYY or DD/MM/YYYY or YYYYMMDD."
    )
    birth_city: str | None = Field(None, description="Birth city (optional filter).")
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
    def _run(self, last_name: str, first_name: str | None = None,
             birth_date: str | None = None, birth_city: str | None = None,
             limit: int = 10) -> str:
        params = {"lastName": last_name}
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
        persons = body.get("persons") or []
        return ok({
            "total": body.get("total", 0),
            "matches": [_flatten_person(p) for p in persons[:limit]],
        })
