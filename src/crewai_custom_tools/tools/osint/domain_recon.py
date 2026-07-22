"""Domain and Certificate Transparency reconnaissance tools (crt.sh & whodap)."""

import logging
import urllib.parse
from datetime import datetime
from typing import Any

import requests
import tldextract
import whodap
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from whodap.utils import WHOISKeys

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


class DomainInput(BaseModel):
    """Input schema for domain-recon tools."""

    domain: str = Field(
        ..., description="The domain to scan or query (e.g., 'example.com')."
    )


class CrtShTool(BaseTool):
    """Enumerates subdomains observed in Certificate Transparency logs via crt.sh."""

    name: str = "crt_sh_subdomain_recon"
    description: str = "Queries crt.sh's public Certificate Transparency logs to find subdomains that have had TLS certificates."
    args_schema: type[BaseModel] = DomainInput

    @api_tool(provider="crtsh", endpoint="Subdomains")
    def _run(self, domain: str) -> str:
        """Search subdomains on crt.sh."""
        clean_domain = domain.strip().lower()
        if not clean_domain or " " in clean_domain:
            return err(f"Invalid domain: {domain!r}")

        encoded_domain = urllib.parse.quote(clean_domain)
        url = f"https://crt.sh/?q=%25.{encoded_domain}&output=json"

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        records = response.json()

        hostnames = set()
        for record in records or []:
            name_value = (
                record.get("name_value", "") if isinstance(record, dict) else ""
            )
            for name in name_value.split("\n"):
                name = name.strip().lower()
                if not name or name.startswith("*."):
                    continue
                hostnames.add(name)

        return ok(sorted(hostnames))


class RDAPDomainTool(BaseTool):
    """Looks up domain registration, registrar, creation date, and nameservers via RDAP."""

    name: str = "rdap_domain_recon"
    description: str = "Structured machine-readable WHOIS lookup using RDAP to fetch domain registrar, creation date, and nameservers."
    args_schema: type[BaseModel] = DomainInput

    @api_tool(provider="RDAP", endpoint="DomainLookup")
    def _run(self, domain: str) -> str:
        """Lookup RDAP registration for the registrable domain using whodap."""
        # Public-suffix-aware parsing: strips subdomains (www.) and handles
        # multi-label suffixes (.co.uk) that a naive rpartition('.') breaks.
        ext = tldextract.extract(domain.strip().lower())
        if not ext.domain or not ext.suffix:
            return err(
                f"Invalid domain: {domain!r}. Must be a registrable domain (e.g. 'google.com')."
            )

        registrable = f"{ext.domain}.{ext.suffix}"
        # whodap resolves the RDAP server from the final TLD label; splitting the
        # registrable domain on its last dot keeps that working for .co.uk too.
        sld, _, tld = registrable.rpartition(".")

        try:
            response = whodap.lookup_domain(sld, tld)
            whois = response.to_whois_dict()
        except Exception as e:
            logger.warning(f"RDAP lookup failed for {registrable}: {e}")
            return err(f"RDAP lookup failed: {e}")

        def _stringify_date(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        def _as_list(value: Any) -> list[str]:
            return list(value) if isinstance(value, list) else []

        registrar = whois.get(WHOISKeys.REGISTRAR_NAME)
        return ok(
            {
                "domain": registrable,
                "registrar": registrar if isinstance(registrar, str) else None,
                "created": _stringify_date(whois.get(WHOISKeys.CREATED_DATE)),
                "nameservers": _as_list(whois.get(WHOISKeys.NAMESERVERS)),
                "source": "RDAP via whodap",
            }
        )
