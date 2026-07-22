"""HTML to PDF compilation and generation tools using WeasyPrint."""

import logging
import os

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)

# Dynamically check WeasyPrint availability at runtime to prevent compile crashes
try:
    from weasyprint import HTML

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    HTML = None
    _weasyprint_error = str(e)


class HtmlToPdfToolSchema(BaseModel):
    """Input schema for HtmlToPdfTool."""

    html_file_path: str = Field(
        ...,
        description="The absolute or relative path to the input HTML file to be converted.",
    )
    output_pdf_path: str = Field(
        ...,
        description="The absolute or relative path where the generated PDF will be saved.",
    )


class HtmlToPdfTool(BaseTool):
    """A tool to compile HTML layouts into beautifully formatted PDF dossiers."""

    name: str = "html_to_pdf_converter"
    description: str = (
        "Converts a given HTML file to a professional PDF document. "
        "Returns the path to the generated PDF upon success, or an error message on failure."
    )
    args_schema: type[BaseModel] = HtmlToPdfToolSchema

    @api_tool(provider="WeasyPrint", endpoint="HTMLToPDF")
    def _run(self, html_file_path: str, output_pdf_path: str) -> str:
        """Run WeasyPrint to generate PDF from HTML."""
        if not WEASYPRINT_AVAILABLE:
            return err(
                "WeasyPrint system library is not available. "
                f"Underlying error: {_weasyprint_error}. Install deps first — "
                "macOS: brew install glib pango cairo weasyprint; "
                "Linux: apt-get install libpango-1.0-0 libcairo2"
            )

        if not os.path.exists(html_file_path):
            return err(f"HTML input file not found at: {html_file_path}")

        # Resolve output directories
        output_dir = os.path.dirname(os.path.abspath(output_pdf_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Write the PDF
        HTML(filename=html_file_path).write_pdf(output_pdf_path)

        if os.path.exists(output_pdf_path):
            return ok(
                {
                    "pdf_path": output_pdf_path,
                    "message": f"Converted '{html_file_path}' to PDF.",
                }
            )
        return err(f"PDF generation failed. File not found at: {output_pdf_path}")
