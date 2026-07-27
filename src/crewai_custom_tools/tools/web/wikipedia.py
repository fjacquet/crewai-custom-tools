"""Wikipedia search and article extraction tools."""

import logging
import urllib.parse
from enum import StrEnum
from typing import Literal

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.core.user_agent import user_agent

logger = logging.getLogger(__name__)


class ArticleAction(StrEnum):
    """Actions that can be performed on a Wikipedia article."""

    GET_SUMMARY = "get_summary"
    GET_ARTICLE = "get_article"
    GET_SECTIONS = "get_sections"


class WikipediaSearchToolInput(BaseModel):
    """Input model for the WikipediaSearchTool."""

    query: str = Field(..., description="The search query for Wikipedia.")
    limit: int = Field(
        default=5, description="The maximum number of results to return."
    )


class WikipediaSearchTool(BaseTool):
    """A tool to search for articles on Wikipedia."""

    name: str = "Wikipedia Search"
    description: str = "Searches Wikipedia for articles matching a query and returns a list of matching titles."
    args_schema: type[BaseModel] = WikipediaSearchToolInput

    @api_tool(provider="Wikipedia", endpoint="Search")
    def _run(self, query: str, limit: int = 5) -> str:
        """Run the Wikipedia search tool using the MediaWiki API."""
        encoded_query = urllib.parse.quote(query)
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={encoded_query}&utf8=&format=json&srlimit={limit}"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        search_results = response.json().get("query", {}).get("search", [])
        return ok([item.get("title") for item in search_results])


class WikipediaArticleToolInput(BaseModel):
    """Input model for the WikipediaArticleTool.

    `action` is a Literal (not the ArticleAction enum): enum classes render as schema
    references, which strict providers (Mistral) reject in function-call schemas —
    a Literal stays inline.
    """

    title: str = Field(..., description="The title of the Wikipedia article.")
    action: Literal["get_summary", "get_article", "get_sections"] = Field(
        default="get_summary",
        description="The action to perform on the article.",
    )


class WikipediaArticleTool(BaseTool):
    """A tool to fetch various types of content from a Wikipedia article."""

    name: str = "Wikipedia Article Fetcher"
    description: str = "Fetches content (summary, full article, or section titles) from a specified Wikipedia article."
    args_schema: type[BaseModel] = WikipediaArticleToolInput

    @api_tool(provider="Wikipedia", endpoint="ArticleFetcher")
    def _run(
        self, title: str, action: ArticleAction = ArticleAction.GET_SUMMARY
    ) -> str:
        """Fetch article content via the English Wikipedia REST/MediaWiki API."""
        encoded_title = urllib.parse.quote(title)

        if action == ArticleAction.GET_SUMMARY:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                return err(f"No Wikipedia page found for '{title}'")
            response.raise_for_status()
            return ok({"title": title, "summary": response.json().get("extract", "")})

        if action == ArticleAction.GET_SECTIONS:
            # Use the parse API's structured section list rather than parsing the
            # plaintext extract (whose '==' header markers are stripped away).
            url = (
                "https://en.wikipedia.org/w/api.php?action=parse&prop=sections"
                f"&page={encoded_title}&format=json"
            )
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                return err(f"No Wikipedia page found for '{title}'")
            sections = [s.get("line") for s in data.get("parse", {}).get("sections", [])]
            return ok({"title": title, "sections": sections})

        # GET_ARTICLE — full plaintext extract.
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
            f"&explaintext=1&titles={encoded_title}&format=json"
        )
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        if not pages or "-1" in pages:
            return err(f"No Wikipedia page found for '{title}'")
        page_data = next(iter(pages.values()))
        return ok({"title": title, "content": page_data.get("extract", "")})


# --- Place enrichment helpers (French Wikipedia) -----------------------------

FRWIKI_API = "https://fr.wikipedia.org/w/api.php"
_UA_PLACES = user_agent("place enrichment")


def frwiki_geosearch(lat: str, lon: str, radius_m: int = 10000,
                     limit: int = 10) -> list[dict]:
    """Articles français géolocalisés autour d'un point (nom + distance en mètres).

    NE PAS l'employer pour retrouver l'article d'une ville : le tri est la distance,
    et les dix articles les plus proches du centre de Lyon sont ses rues et ses
    monuments — l'article 'Lyon' n'y figure pas. La question « où est l'article
    nommé X » se pose par le titre (`frwiki_page_info`) puis se vérifie par la
    position ; celle-ci ne répond qu'à « qu'y a-t-il près de ce point ».
    """
    response = requests.get(FRWIKI_API, params={
        "action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}",
        "gsradius": min(radius_m, 10000), "gslimit": limit, "format": "json"},
        headers={"User-Agent": _UA_PLACES}, timeout=15)
    response.raise_for_status()
    return [{"title": g.get("title", ""), "dist": g.get("dist"),
             "pageid": g.get("pageid")}
            for g in response.json().get("query", {}).get("geosearch", [])]


def frwiki_page_info(title: str, thumb_px: int = 1200) -> dict:
    """Article cherché PAR SON TITRE : URL canonique, miniature, extrait, coordonnées.

    `redirects=1` fait le gros du travail : le nom porté par l'arbre est souvent
    l'exonyme ('München', 'Lenzburg') et la redirection le résout vers l'article
    français ('Munich', 'Lenzbourg'). C'est une identité assertée par Wikipédia,
    qu'aucune similarité de chaînes ne retrouverait.

    `coordinates` est ce qui permet ensuite de VÉRIFIER le titre trouvé : sans
    position, rien ne distingue Paris de Paris (Texas). Une page d'homonymie n'en
    porte pas — d'où `lat`/`lon` à None, qui vaut refus côté appelant.
    """
    response = requests.get(FRWIKI_API, params={
        "action": "query", "titles": title, "redirects": 1,
        "prop": "info|pageimages|extracts|coordinates",
        "inprop": "url", "piprop": "thumbnail|name", "pithumbsize": thumb_px,
        "exintro": 1, "explaintext": 1, "exchars": 300, "format": "json"},
        headers={"User-Agent": _UA_PLACES}, timeout=15)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    thumb = page.get("thumbnail") or {}
    coord = next(iter(page.get("coordinates") or []), {})
    return {"title": page.get("title", title),
            "url": page.get("fullurl", ""),
            "extract": page.get("extract", ""),
            "image_url": thumb.get("source", ""),
            "image_name": page.get("pageimage", ""),
            "lat": coord.get("lat"),
            "lon": coord.get("lon")}


def frwiki_search_geo(name: str, limit: int = 10) -> list[dict]:
    """Articles GÉOLOCALISÉS répondant à une recherche plein texte sur un nom.

    Rattrape ce que `frwiki_page_info` ne peut pas trancher : titre inexistant, ou
    page d'homonymie sans coordonnées ('Valence' -> 'Valence (Drôme)'). Les pages
    sans coordonnées sont écartées ici même — sans position, aucun lien n'est
    vérifiable, et les laisser passer reviendrait à valider sur le nom seul.
    """
    response = requests.get(FRWIKI_API, params={
        "action": "query", "generator": "search", "gsrsearch": name,
        "gsrlimit": limit, "prop": "info|coordinates", "inprop": "url",
        "format": "json"},
        headers={"User-Agent": _UA_PLACES}, timeout=15)
    response.raise_for_status()
    pages = (response.json().get("query") or {}).get("pages") or {}
    hits = []
    for page in pages.values():
        coord = next(iter(page.get("coordinates") or []), {})
        if coord.get("lat") is None:
            continue
        hits.append({"title": page.get("title", ""), "lat": coord["lat"],
                     "lon": coord["lon"], "url": page.get("fullurl", "")})
    return hits
