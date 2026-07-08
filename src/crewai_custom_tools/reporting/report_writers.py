"""HTML report tools that render a caller-supplied HTML body into a styled document.

These differ from ``RenderReportTool`` (which takes structured *sections* of untrusted
text and escapes them): here the caller passes a pre-composed HTML ``body``/``content``
that is inserted as **trusted markup** — the tool's whole purpose is to wrap
agent-authored HTML in a standardized template. Do not feed untrusted third-party HTML
to these tools; use ``RenderReportTool`` (which escapes) for that.
"""

from functools import lru_cache
from pathlib import Path

from crewai.tools import BaseTool
from markupsafe import Markup
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok
from crewai_custom_tools.reporting.html_generator import build_environment, default_template_dir, validate_html


@lru_cache(maxsize=1)
def _report_css() -> str:
    """Load the packaged report stylesheet once (empty string if absent)."""
    css_path = default_template_dir() / "css" / "report.css"
    try:
        return css_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _today() -> str:
    import datetime as _dt

    return _dt.date.today().isoformat()


class ReportingToolInput(BaseModel):
    """Input schema for ReportingTool."""

    report_title: str = Field(..., description="The title for the HTML report.")
    report_body: str = Field(..., description="The report body, as trusted HTML markup.")
    output_file_path: str = Field(..., description="Path where the HTML report should be written.")


class ReportingTool(BaseTool):
    """Render a title + HTML body into the professional template and write it to a file."""

    name: str = "professional_report_generator"
    description: str = (
        "Generate a professional HTML report from a title and an HTML body and save it to a "
        "file. The body must be trusted, well-structured HTML."
    )
    args_schema: type[BaseModel] = ReportingToolInput

    @api_tool(provider="Reporting", endpoint="ProfessionalReport")
    def _run(self, report_title: str, report_body: str, output_file_path: str) -> str:
        """Render the professional template and write the result to ``output_file_path``."""
        template = build_environment().get_template("professional_report_template.html")
        html = template.render(
            report_title=report_title,
            title=report_title,
            generation_date=_today(),
            report_body=Markup(report_body),
        )
        validate_html(html, raise_on_error=True)
        out = Path(output_file_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        return ok({"html_path": str(out), "bytes": len(html)})


class UniversalReportInput(BaseModel):
    """Input schema for UniversalReportTool."""

    title: str = Field(..., description="The title of the report.")
    content: str = Field(..., description="The report body as trusted, well-structured HTML.")


class UniversalReportTool(BaseTool):
    """Wrap a title + HTML content in the standardized universal template and return the HTML."""

    name: str = "universal_report_generator"
    description: str = (
        "Generate a standardized, styled HTML report document from a title and a trusted HTML "
        "content body. Returns the complete HTML document."
    )
    args_schema: type[BaseModel] = UniversalReportInput

    @api_tool(provider="Reporting", endpoint="UniversalReport")
    def _run(self, title: str, content: str) -> str:
        """Render the universal template with the caller's HTML content."""
        template = build_environment().get_template("universal_report_template.html")
        html = template.render(
            report_title=title,
            title=title,
            generation_date=_today(),
            report_body=Markup(content),
            static_css=Markup(_report_css()),
            theme_css_vars="",
        )
        validate_html(html, raise_on_error=True)
        return ok(html)
