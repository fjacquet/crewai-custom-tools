"""CLI-backed OSINT tools: Sherlock, Maigret, theHarvester, net recon.

Each tool shells out to an external binary via the hardened, no-shell
``core.cli_runner``. They are GRACEFULLY GATED: if the required binary is not on
PATH, ``_run`` returns an error envelope instead of raising, so the package
installs and imports everywhere and each tool lights up wherever its binary is
present. Input is validated with ``validate_target`` before ever reaching the
subprocess (argument-injection guard).
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.cli_runner import (
    BinaryMissing,
    CliError,
    CliTimeout,
    available,
    run_cli,
    validate_target,
)
from crewai_custom_tools.core.results import err, ok

_CLI_ERRORS = (BinaryMissing, CliTimeout, CliError, ValueError)


class _UsernameInput(BaseModel):
    """Input schema for the username-recon CLI tools."""

    username: str = Field(..., description="The username to search across sites.")


class _DomainInput(BaseModel):
    """Input schema for the domain-recon CLI tools."""

    domain: str = Field(
        ..., description="The domain to investigate (e.g. 'example.com')."
    )


# --------------------------------------------------------------------------- #
# Sherlock
# --------------------------------------------------------------------------- #

_SHERLOCK_FOUND_RE = re.compile(
    r"^\[\+\]\s*(?:\[\d+ms\]\s*)?(?P<site>[^:]+):\s*(?P<url>\S+)\s*$"
)


def _parse_sherlock(text: str, username: str) -> list[dict]:
    """Parse Sherlock's ``[+] <Site>: <url>`` found-lines into account dicts."""
    accounts = []
    for line in text.splitlines():
        match = _SHERLOCK_FOUND_RE.match(line.strip())
        if match:
            accounts.append(
                {
                    "site": match.group("site").strip(),
                    "url": match.group("url").strip(),
                    "username": username,
                }
            )
    return accounts


class SherlockTool(BaseTool):
    """Search a username across hundreds of sites via the Sherlock CLI."""

    name: str = "sherlock_username_search"
    description: str = (
        "Search a username across hundreds of social sites using the Sherlock CLI. "
        "Requires the external 'sherlock' binary to be installed."
    )
    args_schema: type[BaseModel] = _UsernameInput

    def _run(self, username: str) -> str:
        """Run Sherlock and return the found accounts, or an error envelope."""
        if not available("sherlock"):
            return err("sherlock not installed; install it to use SherlockTool")
        try:
            validate_target(username)
            result = run_cli(
                "sherlock",
                [username, "--print-found", "--no-color", "--no-txt"],
                timeout=120.0,
            )
        except _CLI_ERRORS as exc:
            return err(f"sherlock: {type(exc).__name__}: {exc}")
        if not result.ok:
            return err(f"sherlock: exited with code {result.returncode}")
        accounts = _parse_sherlock(result.stdout, username)
        return ok({"username": username, "accounts": accounts, "count": len(accounts)})


# --------------------------------------------------------------------------- #
# Maigret
# --------------------------------------------------------------------------- #


def _parse_maigret(text: str, username: str) -> list[dict]:
    """Parse Maigret's ``--json ndjson`` report (CLAIMED-only) into account dicts."""
    accounts = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        status = record.get("status") or {}
        site = record.get("site") or {}
        site_name = record.get("sitename") or status.get("site_name")
        url = record.get("url_user") or status.get("url")
        if not site_name or not url:
            continue
        tags = site.get("tags") or status.get("tags") or []
        accounts.append(
            {
                "site": site_name,
                "url": url,
                "username": username,
                "category": tags[0] if tags else None,
            }
        )
    return accounts


class MaigretTool(BaseTool):
    """Search a username across thousands of sites via the Maigret CLI."""

    name: str = "maigret_username_search"
    description: str = (
        "Search a username across thousands of sites (with category tags) using the "
        "Maigret CLI. Requires the external 'maigret' binary to be installed."
    )
    args_schema: type[BaseModel] = _UsernameInput

    def _run(self, username: str) -> str:
        """Run Maigret and return the claimed accounts, or an error envelope."""
        if not available("maigret"):
            return err("maigret not installed; install it to use MaigretTool")
        try:
            validate_target(username)
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_cli(
                    "maigret",
                    [username, "--json", "ndjson", "--folderoutput", tmpdir, "--no-recursion"],
                    timeout=180.0,
                )
                if not result.ok:
                    return err(f"maigret: exited with code {result.returncode}")
                report = Path(tmpdir) / f"report_{username}_ndjson.json"
                if not report.exists():
                    return err("maigret: no JSON report produced")
                text = report.read_text(encoding="utf-8")
        except _CLI_ERRORS as exc:
            return err(f"maigret: {type(exc).__name__}: {exc}")
        except (OSError, UnicodeDecodeError) as exc:
            return err(f"maigret: unreadable report: {exc}")
        accounts = _parse_maigret(text, username)
        return ok({"username": username, "accounts": accounts, "count": len(accounts)})


# --------------------------------------------------------------------------- #
# theHarvester
# --------------------------------------------------------------------------- #

# No-API-key-required passive sources, per theHarvester's README.
_HARVESTER_SOURCES = "baidu,crtsh,hackertarget,otx,rapiddns,urlscan"


class TheHarvesterTool(BaseTool):
    """Collect emails/hosts/names for a domain via the theHarvester CLI."""

    name: str = "theharvester_domain_recon"
    description: str = (
        "Collect emails, hostnames and people for a domain via the theHarvester CLI "
        "(keyless passive sources). Requires the external 'theHarvester' binary."
    )
    args_schema: type[BaseModel] = _DomainInput

    def _run(self, domain: str) -> str:
        """Run theHarvester and return emails/hosts/names, or an error envelope."""
        if not available("theHarvester"):
            return err("theHarvester not installed; install it to use TheHarvesterTool")
        try:
            validate_target(domain)
            with tempfile.TemporaryDirectory() as tmpdir:
                base = Path(tmpdir) / "harvest"
                result = run_cli(
                    "theHarvester",
                    ["-d", domain, "-b", _HARVESTER_SOURCES, "-f", str(base)],
                    timeout=180.0,
                )
                if not result.ok:
                    return err(f"theharvester: exited with code {result.returncode}")
                report = base.with_suffix(".json")
                if not report.exists():
                    return err("theharvester: no JSON report produced")
                data = json.loads(report.read_text(encoding="utf-8"))
        except _CLI_ERRORS as exc:
            return err(f"theharvester: {type(exc).__name__}: {exc}")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return err(f"theharvester: unreadable report: {exc}")
        return ok(
            {
                "domain": domain,
                "emails": sorted({e for e in data.get("emails", []) if e}),
                "hosts": sorted({h for h in data.get("hosts", []) if h}),
                "names": sorted({n for n in data.get("people", []) if n}),
            }
        )


# --------------------------------------------------------------------------- #
# Network recon (subfinder -> dnsx -> httpx)
# --------------------------------------------------------------------------- #


def _parse_jsonl(text: str) -> list[dict]:
    """Parse newline-delimited JSON, skipping blank/unparsable lines."""
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


class NetReconTool(BaseTool):
    """Enumerate subdomains, live hosts and tech via subfinder -> dnsx -> httpx."""

    name: str = "net_recon"
    description: str = (
        "Enumerate subdomains, resolve live hosts, and fingerprint tech for a domain "
        "via the subfinder -> dnsx -> httpx CLI chain. Requires those external binaries."
    )
    args_schema: type[BaseModel] = _DomainInput

    def _run(self, domain: str) -> str:
        """Run the recon chain and return the findings, or an error envelope."""
        for binary in ("subfinder", "dnsx", "httpx"):
            if not available(binary):
                return err(
                    f"{binary} not installed; install subfinder, dnsx and httpx to use NetReconTool"
                )
        try:
            validate_target(domain)
            subfinder = run_cli("subfinder", ["-silent", "-json", "-d", domain], timeout=120.0)
            subs = sorted(
                {r["host"] for r in _parse_jsonl(subfinder.stdout) if r.get("host")}
            )
            dnsx = run_cli(
                "dnsx", ["-silent", "-json", "-resp"], stdin="\n".join(subs), timeout=120.0
            )
            live = sorted({r["host"] for r in _parse_jsonl(dnsx.stdout) if r.get("host")})
            httpx = run_cli(
                "httpx",
                ["-silent", "-json", "-td", "-title"],
                stdin="\n".join(live),
                timeout=120.0,
            )
            tech: set[str] = set()
            hosts: set[str] = set()
            for rec in _parse_jsonl(httpx.stdout):
                tech.update(rec.get("tech") or [])
                host = urlparse(rec.get("url", "")).hostname
                if host:
                    hosts.add(host)
        except _CLI_ERRORS as exc:
            return err(f"net_recon: {type(exc).__name__}: {exc}")
        return ok(
            {
                "domain": domain,
                "subdomains": sorted(set(subs) | hosts),
                "live_hosts": live,
                "tech": sorted(tech),
            }
        )
