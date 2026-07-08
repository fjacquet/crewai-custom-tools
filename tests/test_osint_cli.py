"""Tests for the CLI-backed OSINT tools — fully mocked, no external binaries needed."""

import json

import pytest

from crewai_custom_tools.core.cli_runner import CliResult, validate_target
from crewai_custom_tools.tools.osint import cli_providers as cp
from crewai_custom_tools.tools.osint.cli_providers import (
    MaigretTool,
    NetReconTool,
    SherlockTool,
    TheHarvesterTool,
    _parse_maigret,
    _parse_sherlock,
)


def _env(result):
    """Assert the result is a canonical envelope and return the parsed dict."""
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


@pytest.mark.parametrize(
    "tool_cls,kwargs",
    [
        (SherlockTool, {"username": "alice"}),
        (MaigretTool, {"username": "alice"}),
        (TheHarvesterTool, {"domain": "example.com"}),
        (NetReconTool, {"domain": "example.com"}),
    ],
)
def test_binary_missing_returns_err(mocker, tool_cls, kwargs):
    """Every CLI tool is instantiable and returns err when its binary is absent."""
    mocker.patch.object(cp, "available", return_value=False)
    payload = _env(tool_cls()._run(**kwargs))
    assert payload["success"] is False
    assert "not installed" in payload["error"]


def test_validate_target_rejects_flag_without_running(mocker):
    """A leading-dash target is rejected before the subprocess is ever invoked."""
    mocker.patch.object(cp, "available", return_value=True)
    run = mocker.patch.object(cp, "run_cli")
    payload = _env(SherlockTool()._run(username="-oProxyCommand=evil"))
    assert payload["success"] is False
    run.assert_not_called()


def test_sherlock_parses_found_accounts(mocker):
    """Sherlock stdout is parsed into structured account hits."""
    mocker.patch.object(cp, "available", return_value=True)
    stdout = (
        "[*] Checking username alice on:\n"
        "[+] GitHub: https://github.com/alice\n"
        "[+] Reddit: https://reddit.com/user/alice\n"
        "[*] Search completed with 2 results\n"
    )
    mocker.patch.object(
        cp, "run_cli", return_value=CliResult(ok=True, stdout=stdout, returncode=0)
    )
    payload = _env(SherlockTool()._run(username="alice"))
    assert payload["success"] is True
    assert {a["site"] for a in payload["data"]["accounts"]} == {"GitHub", "Reddit"}
    assert payload["data"]["count"] == 2


def test_netrecon_chains_and_parses(mocker):
    """The subfinder->dnsx->httpx chain is parsed into subdomains/hosts/tech."""
    mocker.patch.object(cp, "available", return_value=True)
    subfinder = CliResult(ok=True, stdout=json.dumps({"host": "a.example.com"}), returncode=0)
    dnsx = CliResult(ok=True, stdout=json.dumps({"host": "a.example.com"}), returncode=0)
    httpx = CliResult(
        ok=True,
        stdout=json.dumps({"url": "https://a.example.com", "tech": ["nginx"]}),
        returncode=0,
    )
    mocker.patch.object(cp, "run_cli", side_effect=[subfinder, dnsx, httpx])
    payload = _env(NetReconTool()._run(domain="example.com"))
    assert payload["success"] is True
    assert "a.example.com" in payload["data"]["subdomains"]
    assert payload["data"]["live_hosts"] == ["a.example.com"]
    assert payload["data"]["tech"] == ["nginx"]


def test_maigret_missing_report_returns_err(mocker):
    """A successful run that produces no report file surfaces an error envelope."""
    mocker.patch.object(cp, "available", return_value=True)
    mocker.patch.object(
        cp, "run_cli", return_value=CliResult(ok=True, stdout="", returncode=0)
    )
    payload = _env(MaigretTool()._run(username="alice"))
    assert payload["success"] is False


def test_parse_helpers():
    """The pure parse helpers extract accounts from Sherlock and Maigret output."""
    sherlock = _parse_sherlock("[+] GitHub: https://github.com/alice", "alice")
    assert sherlock == [
        {"site": "GitHub", "url": "https://github.com/alice", "username": "alice"}
    ]
    ndjson = json.dumps(
        {"sitename": "GitHub", "url_user": "https://github.com/alice", "site": {"tags": ["coding"]}}
    )
    maigret = _parse_maigret(ndjson, "alice")
    assert maigret[0]["site"] == "GitHub"
    assert maigret[0]["category"] == "coding"


def test_validate_target_helper():
    """validate_target accepts safe targets and rejects flags/spaces."""
    assert validate_target("example.com") == "example.com"
    with pytest.raises(ValueError):
        validate_target("-flag")
    with pytest.raises(ValueError):
        validate_target("a b")
