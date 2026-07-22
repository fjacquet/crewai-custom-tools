"""Mock-based unit tests for unified OSINT and corporate registry tools."""

import json
import os

from crewai_custom_tools.tools.osint.corporate_global import OpenCorporatesSearchTool
from crewai_custom_tools.tools.osint.domain_recon import CrtShTool, RDAPDomainTool
from crewai_custom_tools.tools.osint.email_recon import (
    EpieosEmailLookupTool,
    HoleheEmailScannerTool,
    HunterIOTool,
    SerperEmailSearchTool,
)
from crewai_custom_tools.tools.osint.github import GitHubOrgSearchTool, GitHubSearchTool
from crewai_custom_tools.tools.osint.person_recon import UsernameSearchTool
from crewai_custom_tools.tools.osint.registers import FrenchRegistryTool


def _data(result_str):
    """Assert an ok-envelope and return its data payload."""
    payload = json.loads(result_str)
    assert payload["success"] is True, payload
    return payload["data"]


def _error(result_str):
    """Assert an err-envelope and return its message."""
    payload = json.loads(result_str)
    assert payload["success"] is False, payload
    return payload["error"]


def _resp(mocker, *, status=200, json_data=None, text=""):
    r = mocker.MagicMock()
    r.status_code = status
    r.text = text
    if json_data is not None:
        r.json.return_value = json_data
    return r


# ============================== GitHub ==============================


def test_github_search_success(mocker):
    mocker.patch.dict(os.environ, {"GITHUB_TOKEN": "test_gh_token"})
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "total_count": 100,
                "items": [
                    {
                        "full_name": "owner/repo-name",
                        "html_url": "https://github.com/owner/repo-name",
                        "stargazers_count": 42,
                        "forks_count": 7,
                    }
                ],
            },
        ),
    )

    data = _data(GitHubSearchTool()._run(query="OSINT", search_type="repositories"))
    assert data["search_type"] == "repositories"
    assert data["total_count"] == 100
    assert data["results"][0]["name"] == "owner/repo-name"


def test_github_search_missing_key_does_not_drop_all(mocker):
    """One item missing a key must not KeyError-nuke the whole result set (L8)."""
    mocker.patch.dict(os.environ, {"GITHUB_TOKEN": "t"})
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "total_count": 2,
                "items": [{"html_url": "u1"}, {"full_name": "a/b", "html_url": "u2"}],
            },
        ),
    )
    data = _data(GitHubSearchTool()._run(query="x"))
    assert len(data["results"]) == 2
    assert data["results"][0]["name"] is None  # missing full_name → None, not a crash
    assert data["results"][1]["name"] == "a/b"


def test_github_org_search_success(mocker):
    mocker.patch.dict(os.environ, {"GITHUB_TOKEN": "test_gh_token"})
    org = _resp(
        mocker,
        json_data={
            "name": "Acme Org",
            "login": "acme",
            "html_url": "https://github.com/acme",
            "public_repos": 10,
            "followers": 50,
            "repos_url": "https://api.github.com/orgs/acme/repos",
        },
    )
    repos = _resp(
        mocker,
        json_data=[
            {"name": "small", "html_url": "u1", "stargazers_count": 3},
            {"name": "big", "html_url": "u2", "stargazers_count": 99},
        ],
    )
    mocker.patch(
        "requests.get",
        side_effect=lambda url, *a, **k: repos if "repos" in url else org,
    )

    data = _data(GitHubOrgSearchTool()._run(org_name="acme"))
    assert data["exists"] is True
    assert data["name"] == "Acme Org"
    assert data["top_repos"][0]["name"] == "big"  # sorted by stars desc


def test_github_org_search_not_found(mocker):
    mocker.patch.dict(os.environ, {"GITHUB_TOKEN": "t"})
    mocker.patch("requests.get", return_value=_resp(mocker, status=404))
    data = _data(GitHubOrgSearchTool()._run(org_name="nope"))
    assert data["exists"] is False


# ============================== Email ==============================


def test_hunter_io_success(mocker):
    mocker.patch.dict(os.environ, {"HUNTER_API_KEY": "test_hunter_key"})
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={"data": {"domain": "acme.com", "emails": [{"value": "a@acme.com"}]}},
        ),
    )
    data = _data(HunterIOTool()._run(domain="acme.com"))
    assert data["domain"] == "acme.com"


def test_serper_email_search(mocker):
    mocker.patch.dict(os.environ, {"SERPER_API_KEY": "test_serper_key"})
    post = mocker.patch(
        "requests.post",
        return_value=_resp(
            mocker,
            json_data={
                "organic": [
                    {"title": "Contact", "snippet": "info@acme.com or sales@acme.com", "link": "x"}
                ]
            },
        ),
    )
    data = _data(SerperEmailSearchTool()._run(query="Acme Corp"))
    assert "info@acme.com" in data["emails"]
    assert "sales@acme.com" in data["emails"]
    # Balanced-quote query: the domain guess sits inside the quotes.
    assert post.call_args.kwargs["json"]["q"] == '"acme corp" "@acmecorp" email'


def test_serper_email_search_only_serper_key(mocker):
    """A stray SERPAPI key must NOT be used (M3/L10)."""
    mocker.patch.dict(os.environ, {"SERPAPI_API_KEY": "wrong"}, clear=True)
    assert "SERPER_API_KEY" in _error(SerperEmailSearchTool()._run(query="x"))


def test_epieos_keyless_unavailable(mocker):
    """Keyless Epieos now returns an honest error, not success-with-empty-data (H9)."""
    mocker.patch.dict(os.environ, {}, clear=True)
    assert "EPIEOS_API_KEY" in _error(EpieosEmailLookupTool()._run(email="a@b.com"))


def test_epieos_api_success(mocker):
    mocker.patch.dict(os.environ, {"EPIEOS_API_KEY": "k"})
    mocker.patch(
        "requests.get",
        return_value=_resp(mocker, json_data={"email": "a@b.com", "data": {"google": {"name": "T"}}}),
    )
    data = _data(EpieosEmailLookupTool()._run(email="a@b.com"))
    assert data["data"]["google"]["name"] == "T"


def test_holehe_scan_success(mocker):
    mocker.patch(
        "trio.run",
        return_value=[
            {"name": "github", "exists": True, "rateLimit": False, "error": False},
            {"name": "twitter", "exists": False, "rateLimit": False, "error": False},
            {"name": "netflix", "exists": None, "rateLimit": True, "error": False},
        ],
    )
    data = _data(HoleheEmailScannerTool()._run(email="a@b.com"))
    assert [h["name"] for h in data["found"]] == ["github"]
    assert data["undetermined"][0]["name"] == "netflix"  # rate-limited surfaced (M10)
    assert data["checked"] == 3


def test_holehe_scan_import_failure_is_error(mocker):
    mocker.patch("trio.run", side_effect=ImportError("holehe missing"))
    assert "Holehe scan failed" in _error(HoleheEmailScannerTool()._run(email="a@b.com"))


# ============================== Username ==============================


def test_username_search_found_and_unknown(mocker):
    """200→found, 404→not_found, 403→unknown (H7)."""

    def side_effect(url, *a, **k):
        if "github.com" in url:
            return _resp(mocker, status=200, text="<html>profile</html>")
        if "reddit.com" in url:
            return _resp(mocker, status=403)
        return _resp(mocker, status=404)

    mocker.patch("requests.get", side_effect=side_effect)
    data = _data(UsernameSearchTool()._run(username="johndoe"))

    assert [f["platform"] for f in data["found"]] == ["GitHub"]
    assert [u["platform"] for u in data["unknown"]] == ["Reddit"]
    assert data["checked"] == 6


def test_username_search_soft_404_marker(mocker):
    """A 200 login-wall/soft-404 with an absent-marker is NOT a false positive."""

    def side_effect(url, *a, **k):
        if "reddit.com" in url:
            return _resp(mocker, status=200, text="Sorry, nobody on Reddit goes by that name.")
        return _resp(mocker, status=404)

    mocker.patch("requests.get", side_effect=side_effect)
    data = _data(UsernameSearchTool()._run(username="ghost"))
    assert data["found"] == []


def test_username_search_rejects_spaces():
    assert "Invalid username" in _error(UsernameSearchTool()._run(username="a b"))


# ============================== Domain ==============================


def test_crt_sh_subdomain_recon(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data=[
                {"name_value": "api.acme.com\nwww.acme.com"},
                {"name_value": "*.acme.com"},
            ],
        ),
    )
    data = _data(CrtShTool()._run(domain="acme.com"))
    assert "api.acme.com" in data and "www.acme.com" in data
    assert not any(d.startswith("*.") for d in data)


def test_rdap_domain_recon(mocker):
    whois = mocker.MagicMock()
    whois.to_whois_dict.return_value = {
        "registrar_name": "MarkMonitor, Inc.",
        "created_date": "1997-09-15T04:00:00Z",
        "nameservers": ["ns1.google.com", "ns2.google.com"],
    }
    lookup = mocker.patch("whodap.lookup_domain", return_value=whois)

    data = _data(RDAPDomainTool()._run(domain="www.google.com"))
    assert data["domain"] == "google.com"  # subdomain stripped
    assert data["registrar"] == "MarkMonitor, Inc."
    lookup.assert_called_once_with("google", "com")


def test_rdap_multi_label_suffix(mocker):
    """.co.uk must not be mangled by a naive last-dot split (M1)."""
    whois = mocker.MagicMock()
    whois.to_whois_dict.return_value = {}
    lookup = mocker.patch("whodap.lookup_domain", return_value=whois)

    data = _data(RDAPDomainTool()._run(domain="www.example.co.uk"))
    assert data["domain"] == "example.co.uk"
    lookup.assert_called_once_with("example.co", "uk")


# ============================== Registers ==============================


def test_french_registry_search_success(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "results": [
                    {
                        "siren": "123456789",
                        "nom_complet": "ACME FRANCE SAS",
                        "etat_administratif": "A",
                        "siege": {
                            "siret": "12345678900010",
                            "numero_voie": "10",
                            "type_voie": "RUE",
                            "libelle_voie": "DE LA PAIX",
                            "code_postal": "75002",
                            "libelle_commune": "PARIS",
                        },
                        "dirigeants": [{"prenoms": "Jean", "nom": "Dupont"}],
                        "complements": {"site_web": "https://acme.fr"},
                    }
                ]
            },
        ),
    )
    data = _data(FrenchRegistryTool()._run(query="123456789"))
    assert data["siren"] == "123456789"
    assert data["address"] == "10 RUE DE LA PAIX 75002 PARIS"
    assert "Jean Dupont" in data["officers"]


def test_french_registry_keeps_corporate_officer(mocker):
    """personne-morale dirigeants (denomination only) must not be dropped (L6)."""
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "results": [
                    {
                        "siren": "1",
                        "nom_complet": "HOLDCO",
                        "dirigeants": [{"denomination": "PARENT HOLDING SAS"}],
                    }
                ]
            },
        ),
    )
    data = _data(FrenchRegistryTool()._run(query="1"))
    assert "PARENT HOLDING SAS" in data["officers"]


# ============================== OpenCorporates ==============================


def test_opencorporates_search_success(mocker):
    mocker.patch(
        "requests.get",
        return_value=_resp(
            mocker,
            json_data={
                "results": {
                    "companies": [
                        {
                            "company": {
                                "name": "ACME GLOBAL LTD",
                                "company_number": "1234567",
                                "jurisdiction_code": "gb",
                            }
                        }
                    ]
                }
            },
        ),
    )
    data = _data(OpenCorporatesSearchTool()._run(query="ACME", jurisdiction_code="gb"))
    assert data["total_results"] == 1
    assert data["companies"][0]["name"] == "ACME GLOBAL LTD"


def test_opencorporates_anonymous_rejected(mocker):
    """A 401/403 (no token) surfaces a clear error, not an empty result (H9)."""
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("requests.get", return_value=_resp(mocker, status=403))
    assert "OPENCORPORATES_API_KEY" in _error(OpenCorporatesSearchTool()._run(query="x"))
