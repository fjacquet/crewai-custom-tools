"""Offline tests for the free external API tools (fixtures from live probes)."""

import json

from crewai_custom_tools.tools.genealogy.matchid import InseeDecesSearchTool
from crewai_custom_tools.tools.web.gallica import GallicaSearchTool, parse_sru
from crewai_custom_tools.tools.web.wikidata import WikidataSparqlTool


def _data(result_str):
    payload = json.loads(result_str)
    assert payload["success"] is True, payload
    return payload["data"]


# --- wikidata_sparql ---

SPARQL_PAYLOAD = {
    "head": {"vars": ["item", "itemLabel"]},
    "results": {"bindings": [
        {"item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q91874111"},
         "itemLabel": {"type": "literal", "value": "Q91874111"}},
        {"item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q92563334"},
         "itemLabel": {"type": "literal", "value": "Q92563334"}},
    ]},
}


def test_wikidata_flattens_bindings_and_truncates(mocker):
    resp = mocker.MagicMock()
    resp.json.return_value = SPARQL_PAYLOAD
    get = mocker.patch("crewai_custom_tools.tools.web.wikidata.requests.get",
                       return_value=resp)
    data = _data(WikidataSparqlTool()._run(query="SELECT ...", limit=1))
    assert data["variables"] == ["item", "itemLabel"]
    assert data["count"] == 1 and data["truncated"] is True
    assert data["rows"][0]["item"].endswith("Q91874111")
    # endpoint + format json + User-Agent posés
    _, kwargs = get.call_args
    assert kwargs["params"]["format"] == "json"
    assert "User-Agent" in kwargs["headers"]


# --- gallica_search ---

SRU_XML = """<?xml version="1.0" encoding="UTF-8"?>
<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/"
    xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
    xmlns:dc="http://purl.org/dc/elements/1.1/">
  <srw:numberOfRecords>913</srw:numberOfRecords>
  <srw:records>
    <srw:record>
      <srw:recordData><oai_dc:dc>
        <dc:creator>Société centrale d'agriculture (Aude). Auteur du texte</dc:creator>
        <dc:date>1920-1935</dc:date>
        <dc:identifier>https://gallica.bnf.fr/ark:/12148/cb32723634z/date</dc:identifier>
        <dc:identifier>NUMP-25731</dc:identifier>
        <dc:title>Bulletin de la Société centrale d'agriculture de l'Aude</dc:title>
        <dc:type>text</dc:type>
      </oai_dc:dc></srw:recordData>
    </srw:record>
  </srw:records>
</srw:searchRetrieveResponse>"""


def test_parse_sru_extracts_dublin_core():
    parsed = parse_sru(SRU_XML)
    assert parsed["total"] == 913
    rec = parsed["records"][0]
    assert rec["title"].startswith("Bulletin de la Société")
    assert rec["date"] == "1920-1935"
    assert rec["url"] == "https://gallica.bnf.fr/ark:/12148/cb32723634z/date"


def test_gallica_wraps_plain_terms_in_cql(mocker):
    resp = mocker.MagicMock()
    resp.text = SRU_XML
    get = mocker.patch("crewai_custom_tools.tools.web.gallica.requests.get",
                       return_value=resp)
    data = _data(GallicaSearchTool()._run(query="Villaudy Bourges", max_records=5))
    assert data["query"] == 'gallica all "Villaudy Bourges"'
    assert data["total"] == 913 and len(data["records"]) == 1
    _, kwargs = get.call_args
    assert kwargs["params"]["maximumRecords"] == 5


# --- insee_deces_search ---

MATCHID_PAYLOAD = {"response": {"total": 1, "persons": [{
    "score": 0.86,
    "name": {"first": ["Odette", "Henriette"], "last": "Rippert"},
    "sex": "F",
    "birth": {"date": "19220929",
              "location": {"city": "Departement De Constantine", "country": "Algerie"}},
    "death": {"date": "20211219", "age": 99,
              "location": {"city": "Bourges", "country": "France"}},
}]}}


def test_insee_deces_flattens_match(mocker):
    resp = mocker.MagicMock()
    resp.json.return_value = MATCHID_PAYLOAD
    get = mocker.patch("crewai_custom_tools.tools.genealogy.matchid.requests.get",
                       return_value=resp)
    data = _data(InseeDecesSearchTool()._run(
        last_name="Rippert", first_name="Odette", birth_date="1922"))
    assert data["total"] == 1
    m = data["matches"][0]
    assert m["prenoms"] == "Odette Henriette" and m["nom"] == "Rippert"
    assert m["deces_date"] == "20211219" and m["deces_lieu"] == "Bourges, France"
    assert m["age_au_deces"] == 99
    _, kwargs = get.call_args
    assert kwargs["params"] == {"lastName": "Rippert", "firstName": "Odette",
                                "birthDate": "1922"}
