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

logger = logging.getLogger(__name__)


def validate_html(html: str, raise_on_error: bool = True) -> bool:
    """Validate HTML structure using BeautifulSoup4."""
    soup = BeautifulSoup(html, "html.parser")

    if not soup.body:
        if raise_on_error:
            raise ValueError("HTML validation failed: Missing required <body> element")
        return False

    return True


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
        if template_dir:
            self._template_dir = Path(template_dir)
        else:
            # Locate the templates directory inside project root
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self._template_dir = project_root / "templates"

        if not self._template_dir.exists():
            # Fallback check
            self._template_dir = Path("./templates")

        if not self._template_dir.exists():
            raise FileNotFoundError(
                f"HTML templates directory not found: {self._template_dir}"
            )

        self._env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
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

    @api_tool(
        provider="Jinja2",
        endpoint="RenderReport",
        default_return="Error rendering HTML report.",
    )
    def _run(self, title: str, sections: List[dict], **kwargs: Any) -> str:
        """Render standard template with context."""
        template_name = kwargs.get("template_name") or "report_template.html"
        template = self._env.get_template(template_name)

        context = {
            "title": title,
            "date": _dt.date.today().isoformat(),
            "sections": sections,
            "images": kwargs.get("images") or [],
            "citations": kwargs.get("citations") or [],
        }

        html = template.render(**context)
        validate_html(html, raise_on_error=True)
        return html
