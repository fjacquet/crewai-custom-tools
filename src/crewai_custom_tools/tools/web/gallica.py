"""Gallica (BnF) SRU search tool — free digital-archive search."""

import logging
import xml.etree.ElementTree as ET

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok

logger = logging.getLogger(__name__)

SRU_ENDPOINT = "https://gallica.bnf.fr/SRU"
USER_AGENT = "crewai-custom-tools/genealogy (research tool)"
_NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _dc_values(record: ET.Element, field: str) -> list[str]:
    return [e.text.strip() for e in record.findall(f".//dc:{field}", _NS) if e.text]


def parse_sru(xml_text: str) -> dict:
    """Parse an SRU searchRetrieve response into total + flat records. Pure."""
    root = ET.fromstring(xml_text)
    total_el = root.find("srw:numberOfRecords", _NS)
    total = int(total_el.text) if total_el is not None and total_el.text else 0
    records = []
    for rec in root.findall(".//srw:record", _NS):
        identifiers = _dc_values(rec, "identifier")
        records.append({
            "title": next(iter(_dc_values(rec, "title")), ""),
            "creator": next(iter(_dc_values(rec, "creator")), ""),
            "date": next(iter(_dc_values(rec, "date")), ""),
            "type": next(iter(_dc_values(rec, "type")), ""),
            "url": next((i for i in identifiers if i.startswith("http")), ""),
        })
    return {"total": total, "records": records}


class GallicaSearchInput(BaseModel):
    """Input model for the GallicaSearchTool."""

    query: str = Field(
        ...,
        description='CQL query, e.g. gallica all "Villaudy Bourges" — or plain terms, '
        "which are wrapped as gallica all \"...\" automatically.",
    )
    max_records: int = Field(10, description="Max records returned (SRU maximumRecords).")


class GallicaSearchTool(BaseTool):
    """Searches the BnF Gallica digital library through its SRU API."""

    name: str = "gallica_search"
    description: str = (
        "Searches Gallica (BnF digitized press, books, archives) with a CQL query and "
        "returns matching documents (title, creator, date, ark URL). Free API — useful "
        "to find period sources mentioning a family name or place."
    )
    args_schema: type[BaseModel] = GallicaSearchInput

    @api_tool(provider="Gallica", endpoint="SRU", timeout=30.0)
    def _run(self, query: str, max_records: int = 10) -> str:
        cql = query if " all " in query or " any " in query else f'gallica all "{query}"'
        response = requests.get(
            SRU_ENDPOINT,
            params={"operation": "searchRetrieve", "version": "1.2",
                    "query": cql, "maximumRecords": max_records},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        parsed = parse_sru(response.text)
        return ok({"query": cql, **parsed})
