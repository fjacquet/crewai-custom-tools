"""Mock-based unit tests for the Phase-2 OSINT provider tools."""

import json
import os

from crewai_custom_tools.tools.osint.hunter_extra import (
    HunterEmailFinderTool,
    HunterEmailVerifierTool,
)
from crewai_custom_tools.tools.osint.registers_extra import BodaccTool, InseeSireneTool
from crewai_custom_tools.tools.osint.signals import GdeltTool, GoogleNewsRssTool


def _envelope(result: str) -> dict:
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


def _resp(mocker, json_value):
    resp = mocker.MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_value
    return resp


# --- INSEE Sirene (keyed) ---------------------------------------------------


def test_insee_missing_key_returns_error(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _envelope(InseeSireneTool()._run(siren="552100554"))
    assert payload["success"] is False
    assert "INSEE_SIRENE_API_KEY" in payload["error"]


def test_insee_maps_authoritative_fields(mocker):
    mocker.patch.dict(os.environ, {"INSEE_SIRENE_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            {
                "uniteLegale": {
                    "siren": "552100554",
                    "denominationUniteLegale": "TOTALENERGIES SE",
                    "trancheEffectifsUniteLegale": "52",
                    "periodesUniteLegale": [
                        {
                            "activitePrincipaleUniteLegale": "70.10Z",
                            "etatAdministratifUniteLegale": "A",
                        }
                    ],
                }
            },
        ),
    )
    payload = _envelope(InseeSireneTool()._run(siren="552100554"))
    assert payload["success"] is True
    data = payload["data"]
    assert data["name"] == "TOTALENERGIES SE"
    assert data["naf"] == "70.10Z"
    assert data["workforce_band"] == "52"
    assert data["active"] is True


# --- BODACC (keyless) -------------------------------------------------------


def test_bodacc_classifies_events(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            {
                "results": [
                    {
                        "dateparution": "2025-02-01",
                        "familleavis_lib": "Procédures collectives",
                        "typeavis_lib": "Annonce",
                        "commercant": "ACME SARL",
                        "jugement": {"nature": "Liquidation judiciaire"},
                    },
                    {
                        "dateparution": "2024-06-01",
                        "familleavis_lib": "Créations d'établissement",
                        "commercant": "ACME SARL",
                    },
                ]
            },
        ),
    )
    payload = _envelope(BodaccTool()._run(siren="123456789"))
    assert payload["success"] is True
    events = payload["data"]["events"]
    assert events[0]["family"] == "insolvency"
    assert events[1]["family"] == "creation"


# --- GDELT (keyless) --------------------------------------------------------


def test_gdelt_maps_articles(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            {
                "articles": [
                    {
                        "title": "Acme raises funding",
                        "url": "https://news.example/acme",
                        "domain": "news.example",
                        "seendate": "20250201T120000Z",
                    },
                    {"title": None, "url": "https://skip.example"},  # dropped
                ]
            },
        ),
    )
    payload = _envelope(GdeltTool()._run(name="Acme"))
    assert payload["success"] is True
    assert len(payload["data"]["articles"]) == 1
    assert payload["data"]["articles"][0]["domain"] == "news.example"


# --- Google News RSS (keyless) ---------------------------------------------


def test_google_news_rss_maps_entries(mocker):
    feed = {
        "entries": [
            {
                "title": "Acme in the news",
                "link": "https://news.example/story",
                "source": {"href": "https://news.example"},
                "published": "Mon, 01 Feb 2025 12:00:00 GMT",
            },
            {"title": "No link"},  # dropped
        ]
    }
    mocker.patch("feedparser.parse", return_value=feed)
    payload = _envelope(GoogleNewsRssTool()._run(name="Acme"))
    assert payload["success"] is True
    articles = payload["data"]["articles"]
    assert len(articles) == 1
    assert articles[0]["domain"] == "news.example"


# --- Hunter finder / verifier (keyed) --------------------------------------


def test_hunter_finder_missing_key(mocker):
    mocker.patch.dict(os.environ, {}, clear=True)
    payload = _envelope(
        HunterEmailFinderTool()._run(first_name="Jane", last_name="Doe", domain="acme.com")
    )
    assert payload["success"] is False
    assert "HUNTER_API_KEY" in payload["error"]


def test_hunter_finder_returns_data(mocker):
    mocker.patch.dict(os.environ, {"HUNTER_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_resp(mocker, {"data": {"email": "jane@acme.com", "score": 97}}),
    )
    payload = _envelope(
        HunterEmailFinderTool()._run(first_name="Jane", last_name="Doe", domain="acme.com")
    )
    assert payload["success"] is True
    assert payload["data"]["email"] == "jane@acme.com"


def test_hunter_verifier_returns_status(mocker):
    mocker.patch.dict(os.environ, {"HUNTER_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_resp(mocker, {"data": {"email": "jane@acme.com", "status": "valid"}}),
    )
    payload = _envelope(HunterEmailVerifierTool()._run(email="jane@acme.com"))
    assert payload["success"] is True
    assert payload["data"]["status"] == "valid"
