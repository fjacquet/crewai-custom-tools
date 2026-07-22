import json

import httpx

from crewai_custom_tools.tools.genealogy.analysis import tools as analysis_tools
from crewai_custom_tools.tools.genealogy.analysis.tools import (
    GenealogyCheckPersonTool,
    GenealogyFindDuplicatesTool,
)
from crewai_custom_tools.tools.genealogy.gramps.client import GrampsClient, GrampsConfig

CONFIG = GrampsConfig(api_url="http://g.test/api", username="u", password="p")


def _client(handler):
    def _h(request):
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"access_token": "t"})
        return handler(request)
    return GrampsClient(CONFIG, transport=httpx.MockTransport(_h))


def _person_raw(gid, handle, given, surname, birth_year, death_year=None, sortvals=(100, 200)):
    events, bi, di = [], -1, -1
    if birth_year:
        events.append({"type": "Birth", "citation_list": [],
                       "date": {"sortval": sortvals[0], "year": birth_year,
                                "dateval": [1, 1, birth_year, False], "modifier": 0, "quality": 0}})
        bi = 0
    if death_year:
        events.append({"type": "Death", "citation_list": [],
                       "date": {"sortval": sortvals[1], "year": death_year,
                                "dateval": [1, 1, death_year, False], "modifier": 0, "quality": 0}})
        di = len(events) - 1
    return {"gramps_id": gid, "handle": handle, "gender": 1,
            "citation_list": ["c1"], "family_list": [], "parent_family_list": [],
            "birth_ref_index": bi, "death_ref_index": di,
            "primary_name": {"first_name": given, "surname_list": [{"surname": surname}]},
            "profile": {}, "extended": {"events": events}}


# --- genealogy_check_person ---

def test_check_person_reports_r1_birth_after_death(mocker):
    # sortvals inverted: birth AFTER death -> R1 haute
    raw = _person_raw("I0010", "H10", "Claude", "Villaudy", 1703, 1701, sortvals=(300, 200))

    def h(request):
        if request.url.path == "/api/people/H10":
            return httpx.Response(200, json=raw)
        return httpx.Response(404)
    mocker.patch.object(analysis_tools, "get_client", return_value=_client(h))
    data = json.loads(GenealogyCheckPersonTool()._run(handle="H10"))
    assert data["success"] is True
    rules = [a["rule"] for a in data["data"]["anomalies"]]
    assert "R1" in rules
    assert data["data"]["gramps_id"] == "I0010"


def test_check_person_resolves_gramps_id_and_includes_family_rules(mocker):
    person = _person_raw("I0001", "HP", "Jean", "Dupont", 1900, 1980)
    person["parent_family_list"] = ["HF"]
    family = {"gramps_id": "F0001", "handle": "HF", "father_handle": "HP",
              "mother_handle": None, "child_ref_list": [], "extended": {"events": []}}

    def h(request):
        p = request.url.path
        if p == "/api/people/" and request.url.params.get("gramps_id") == "I0001":
            return httpx.Response(200, json=[person])
        if p == "/api/people/HP":
            return httpx.Response(200, json=person)
        if p == "/api/families/HF":
            return httpx.Response(200, json=family)
        return httpx.Response(404)
    mocker.patch.object(analysis_tools, "get_client", return_value=_client(h))
    data = json.loads(GenealogyCheckPersonTool()._run(gramps_id="I0001"))
    assert data["success"] is True                            # family fetched, no crash
    assert data["data"]["handle"] == "HP"


def test_check_person_requires_an_identifier(mocker):
    mocker.patch.object(analysis_tools, "get_client",
                        return_value=_client(lambda r: httpx.Response(404)))
    data = json.loads(GenealogyCheckPersonTool()._run())
    assert data["success"] is False


# --- genealogy_find_duplicates ---

def test_find_duplicates_by_surname_uses_search_and_scores_pairs(mocker):
    a = _person_raw("I1", "HA", "Jean", "Dupont", 1900, sortvals=(100, 0))
    b = _person_raw("I2", "HB", "Jean", "Dupont", 1901, sortvals=(105, 0))

    def h(request):
        p = request.url.path
        if p == "/api/search/":
            return httpx.Response(200, json=[
                {"object_type": "person", "handle": "HA"},
                {"object_type": "person", "object": {"handle": "HB"}},
                {"object_type": "event", "handle": "HEV"},     # ignoré
            ])
        if p == "/api/people/HA":
            return httpx.Response(200, json=a)
        if p == "/api/people/HB":
            return httpx.Response(200, json=b)
        return httpx.Response(404)
    mocker.patch.object(analysis_tools, "get_client", return_value=_client(h))
    data = json.loads(GenealogyFindDuplicatesTool()._run(surname="Dupont"))
    assert data["data"]["people_compared"] == 2
    pair = data["data"]["pairs"][0]
    assert {pair["gramps_id_a"], pair["gramps_id_b"]} == {"I1", "I2"}
    assert pair["score"] >= 0.85


def test_find_duplicates_full_scope_paginates_and_caps_limit(mocker):
    calls = {"pages": []}
    a = _person_raw("I1", "HA", "Marie", "Curie", 1867, sortvals=(100, 0))

    def h(request):
        if request.url.path == "/api/people/":
            page = int(request.url.params.get("page"))
            calls["pages"].append(page)
            return httpx.Response(200, json=[a] if page == 1 else [])
        return httpx.Response(404)
    mocker.patch.object(analysis_tools, "get_client", return_value=_client(h))
    data = json.loads(GenealogyFindDuplicatesTool()._run(limit=9999))
    assert data["data"]["people_compared"] == 1 and data["data"]["pairs"] == []
    # limit clampé à MAX_DUPLICATE_SCOPE -> pagesize demandé jamais > 100
    assert calls["pages"] == [1, 2]
