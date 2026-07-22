"""Specialized HTML Layout Template Renderers."""

import logging
from typing import Any

from crewai_custom_tools.reporting.html_generator import RenderReportTool

logger = logging.getLogger(__name__)


class PestelReportRenderer(RenderReportTool):
    """Specialized renderer for PESTEL Analysis (Political, Economic, Social, Technological, Environmental, Legal) reports."""

    name: str = "render_pestel_report"
    description: str = (
        "Renders a professional, beautifully styled PESTEL report using the professional HTML layout template. "
        "Inputs require: title, sections (PESTEL elements list), and optional images and citations."
    )

    def _run(self, title: str, sections: list[dict], **kwargs: Any) -> str:
        """Force the professional report template for PESTEL."""
        kwargs["template_name"] = "professional_report_template.html"
        return super()._run(title, sections, **kwargs)


class FinancialReportRenderer(RenderReportTool):
    """Specialized renderer for Financial and quantitative metrics data reports."""

    name: str = "render_financial_report"
    description: str = (
        "Renders a standard financial report showing quantitative lists and charts using the data report template. "
        "Inputs require: title, sections (financial indicators), and optional images and citations."
    )

    def _run(self, title: str, sections: list[dict], **kwargs: Any) -> str:
        """Force the data report template for Financial tables."""
        kwargs["template_name"] = "data_report_template.html"
        return super()._run(title, sections, **kwargs)
