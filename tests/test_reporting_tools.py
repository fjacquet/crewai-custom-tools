"""Tests for the HTML and PDF reporting tools.

These render the REAL bundled templates (no mocked Jinja Environment) so that a
context/variable mismatch surfaces as a failing test instead of a silently empty
or error report.
"""

import json

import pytest

from crewai_custom_tools.reporting.html_generator import RenderReportTool, validate_html
from crewai_custom_tools.reporting.pdf_generator import HtmlToPdfTool
from crewai_custom_tools.reporting.template_renderers import (
    FinancialReportRenderer,
    PestelReportRenderer,
)

SECTIONS = [
    {"heading": "Political Landscape", "content": "Regulatory stability is improving."},
    {"heading": "Revenue", "content": "10M USD in Q2."},
]


def _html(result: str) -> str:
    """Assert the result is a success envelope and return the rendered HTML."""
    payload = json.loads(result)
    assert payload["success"] is True, payload
    assert payload["error"] is None
    return payload["data"]


def test_html_validator():
    """HTML structural validation requires a <body> element."""
    valid_html = "<html><head><title>T</title></head><body><h1>Hi</h1></body></html>"
    invalid_html = "<html><head><title>T</title></head></html>"

    assert validate_html(valid_html) is True
    with pytest.raises(ValueError, match="Missing required <body> element"):
        validate_html(invalid_html, raise_on_error=True)


@pytest.mark.parametrize(
    "tool_cls",
    [RenderReportTool, PestelReportRenderer, FinancialReportRenderer],
)
def test_renderer_produces_nonempty_report_with_sections(tool_cls):
    """Every renderer returns non-empty HTML in which the sections are visible (H2/H3)."""
    html = _html(tool_cls()._run(title="Acme Report", sections=SECTIONS))

    assert "Acme Report" in html
    # The provided section headings and content must actually appear in the output.
    assert "Political Landscape" in html
    assert "Regulatory stability is improving." in html
    assert "Revenue" in html


@pytest.mark.parametrize(
    "tool_cls",
    [RenderReportTool, PestelReportRenderer, FinancialReportRenderer],
)
def test_renderer_escapes_untrusted_section_content(tool_cls):
    """A <script> in section content is escaped, never emitted raw (M8 stored XSS)."""
    malicious = [{"heading": "Injected", "content": "<script>alert('xss')</script>"}]
    html = _html(tool_cls()._run(title="Sec", sections=malicious))

    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;" in html


def test_financial_renderer_uses_data_template():
    """FinancialReportRenderer renders the data template (timestamp block present)."""
    html = _html(FinancialReportRenderer()._run(title="Q2", sections=SECTIONS))
    assert "Generated on:" in html  # data_report_template header


def test_html_to_pdf_success_envelope(mocker):
    """A successful conversion returns ok({pdf_path})."""
    mocker.patch("crewai_custom_tools.reporting.pdf_generator.WEASYPRINT_AVAILABLE", True)
    mock_html = mocker.MagicMock()
    mocker.patch(
        "crewai_custom_tools.reporting.pdf_generator.HTML", return_value=mock_html
    )
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.makedirs")

    result = HtmlToPdfTool()._run(
        html_file_path="/path/report.html", output_pdf_path="/path/out.pdf"
    )
    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["data"]["pdf_path"] == "/path/out.pdf"
    mock_html.write_pdf.assert_called_once_with("/path/out.pdf")


def test_html_to_pdf_missing_input_returns_error_envelope(mocker):
    """A missing input file returns an error envelope, not a success string."""
    mocker.patch("crewai_custom_tools.reporting.pdf_generator.WEASYPRINT_AVAILABLE", True)
    mocker.patch("os.path.exists", return_value=False)

    payload = json.loads(
        HtmlToPdfTool()._run(
            html_file_path="/nope.html", output_pdf_path="/out.pdf"
        )
    )
    assert payload["success"] is False
    assert "not found" in payload["error"]
