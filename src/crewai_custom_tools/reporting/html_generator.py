"""Standard HTML Report Generation and Validation tools."""

import datetime as _dt
import logging
from pathlib import Path
from typing import Any, List, Optional
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok
from markupsafe import Markup, escape

logger = logging.getLogger(__name__)


def validate_html(html: str, raise_on_error: bool = True) -> bool:
    """Validate HTML structure using BeautifulSoup4."""
    soup = BeautifulSoup(html, "html.parser")

    if not soup.body:
        if raise_on_error:
            raise ValueError("HTML validation failed: Missing required <body> element")
        return False

    return True


def _sections_to_html(sections: Optional[List[dict]]) -> Markup:
    """Build a safe HTML body from sections, escaping all caller-supplied text.

    Returned as ``Markup`` so ``{{ report_body }}`` renders the wrapper tags while the
    heading/content — which may originate from untrusted scraped data — stay escaped.
    """
    parts = []
    for section in sections or []:
        heading = escape(str(section.get("heading", "")))
        content = escape(str(section.get("content", "")))
        parts.append(f"<section><h2>{heading}</h2><div>{content}</div></section>")
    return Markup("".join(parts))


def _build_context(title: str, sections: Optional[List[dict]], **kwargs: Any) -> dict:
    """Assemble a render context that satisfies every bundled template.

    The standard, professional (PESTEL) and data (financial) templates use different
    variable names for the same values (``title``/``report_title``,
    ``date``/``generation_date``/``timestamp``, ``sections``/``report_body``), so we
    supply all of them plus empty defaults for the data template's optional blocks.
    """
    now = _dt.datetime.now()
    today = now.date().isoformat()
    return {
        "title": title,
        "report_title": title,
        "date": today,
        "generation_date": today,
        "timestamp": now,
        "description": kwargs.get("description") or "",
        "sections": sections or [],
        "report_body": _sections_to_html(sections),
        "images": kwargs.get("images") or [],
        "citations": kwargs.get("citations") or [],
        "kpis": kwargs.get("kpis") or [],
        "metrics": kwargs.get("metrics") or [],
        "data_tables": kwargs.get("data_tables") or [],
        "data_series": kwargs.get("data_series") or [],
    }


def default_template_dir() -> Path:
    """Resolve the packaged templates directory (works in editable + wheel installs)."""
    return Path(__file__).resolve().parent / "templates"


def build_environment(template_dir: Optional[Any] = None) -> Environment:
    """Build an autoescaping Jinja2 Environment over the templates directory."""
    tdir = Path(template_dir) if template_dir else default_template_dir()
    if not tdir.exists():
        raise FileNotFoundError(f"HTML templates directory not found: {tdir}")
    return Environment(
        loader=FileSystemLoader(str(tdir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


class RenderReportToolSchema(BaseModel):
    """Input schema for RenderReportTool."""

    title: str = Field(..., description="The title of the HTML report.")
    sections: List[dict] = Field(
        ..., description="A list of sections, each with 'heading' and 'content' keys."
    )
    images: Optional[List[dict]] = Field(
        default=None,
        description="Optional: list of image dicts with 'src', 'alt', 'caption'.",
    )
    citations: Optional[List[str]] = Field(
        default=None, description="Optional: list of citation strings or URLs."
    )
    template_name: Optional[str] = Field(
        default="report_template.html",
        description="The template file to use (e.g. 'report_template.html', 'professional_report_template.html').",
    )


class RenderReportTool(BaseTool):
    """Tool for rendering standardized, visually stunning HTML reports."""

    _env: Environment = PrivateAttr()
    _template_dir: Path = PrivateAttr()

    name: str = "render_html_report"
    description: str = (
        "Renders a standardized HTML report using a Jinja2 template and context values. "
        "Inputs require: title, sections (list of dict with 'heading' and 'content'), and optional images and citations."
    )
    args_schema: type[BaseModel] = RenderReportToolSchema

    def __init__(self, template_dir: Optional[str] = None, **kwargs: Any):
        """Initialize the Jinja2 environment."""
        super().__init__(**kwargs)
        # Templates are packaged inside the reporting/ package, so this resolves
        # correctly in an editable checkout AND a wheel install (site-packages).
        self._template_dir = Path(template_dir) if template_dir else default_template_dir()
        self._env = build_environment(self._template_dir)
        self._env.filters["date"] = self._format_date

    @staticmethod
    def _format_date(date_str: str) -> str:
        """Jinja2 filter to format an ISO date string to a readable format."""
        if not date_str:
            return ""
        try:
            date_obj = _dt.datetime.fromisoformat(
                date_str.replace("Z", "+00:00")
            ).date()
            return date_obj.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            return date_str

    @api_tool(provider="Jinja2", endpoint="RenderReport")
    def _run(self, title: str, sections: List[dict], **kwargs: Any) -> str:
        """Render the selected template with a context that satisfies every template."""
        template_name = kwargs.get("template_name") or "report_template.html"
        template = self._env.get_template(template_name)
        html = template.render(**_build_context(title, sections, **kwargs))
        validate_html(html, raise_on_error=True)
        return ok(html)
