"""Domain and Certificate Transparency reconnaissance tools (crt.sh & whodap)."""

import json
import logging
import urllib.parse
from datetime import datetime
import requests
import whodap
from whodap.utils import WHOISKeys
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


class DomainInput(BaseModel):
    """Input schema for domain-recon tools."""

    domain: str = Field(
        ..., description="The apex domain to scan or query (e.g., 'example.com')."
    )


class CrtShTool(BaseTool):
    """Enumerates subdomains observed in Certificate Transparency logs via crt.sh."""

    name: str = "crt_sh_subdomain_recon"
    description: str = "Queries crt.sh's public Certificate Transparency logs to find subdomains that have had TLS certificates."
    args_schema: type[BaseModel] = DomainInput

    @api_tool(provider="crtsh", endpoint="Subdomains", default_return="[]")
    def _run(self, domain: str) -> str:
        """Search subdomains on crt.sh."""
        clean_domain = domain.strip().lower()
        if not clean_domain or " " in clean_domain:
            return json.dumps([])

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

        return json.dumps(sorted(list(hostnames)))


class RDAPDomainTool(BaseTool):
    """Looks up domain registration, registrar, creation date, and nameservers via RDAP."""

    name: str = "rdap_domain_recon"
    description: str = "Structured machine-readable WHOIS lookup using RDAP to fetch domain registrar, creation date, and nameservers."
    args_schema: type[BaseModel] = DomainInput

    @api_tool(provider="RDAP", endpoint="DomainLookup", default_return="{}")
    def _run(self, domain: str) -> str:
        """Lookup RDAP domain registrations using whodap."""
        clean_domain = domain.strip().lower()
        label, _, tld = clean_domain.rpartition(".")
        if not label or not tld:
            return json.dumps(
                {
                    "error": f"Invalid domain: {domain}. Must contain label and TLD (e.g. 'google.com')."
                }
            )

        try:
            # Execute synchronous whodap lookup
            response = whodap.lookup_domain(label, tld)
            whois = response.to_whois_dict()
        except Exception as e:
            logger.warning(f"RDAP lookup failed for {domain}: {e}")
            return json.dumps({"error": f"RDAP lookup failed: {e}"})

        def _stringify_date(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        def _as_list(value: Any) -> List[str]:
            return list(value) if isinstance(value, list) else []

        result = {
            "domain": clean_domain,
            "registrar": whois.get(WHOISKeys.REGISTRAR_NAME)
            if isinstance(whois.get(WHOISKeys.REGISTRAR_NAME), str)
            else None,
            "created": _stringify_date(whois.get(WHOISKeys.CREATED_DATE)),
            "nameservers": _as_list(whois.get(WHOISKeys.NAMESERVERS)),
            "source": "RDAP via whodap",
        }
        return json.dumps(result)
