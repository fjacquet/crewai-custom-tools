"""Mock-based unit tests for unified HTML and PDF reporting tools."""

import json
import os
import pytest
from unittest.mock import MagicMock
from crewai_custom_tools.reporting.html_generator import RenderReportTool, validate_html
from crewai_custom_tools.reporting.pdf_generator import HtmlToPdfTool
from crewai_custom_tools.reporting.template_renderers import (
    PestelReportRenderer,
    FinancialReportRenderer,
)


# ==============================================================================
# 1. HTML Generator and Validator Tests
# ==============================================================================


def test_html_validator():
    """Test HTML structural validation."""
    valid_html = (
        "<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>"
    )
    invalid_html = "<html><head><title>Test</title></head></html>"  # Missing <body>

    assert validate_html(valid_html) is True

    with pytest.raises(ValueError, match="Missing required <body> element"):
        validate_html(invalid_html, raise_on_error=True)


def test_render_report_tool_success(mocker):
    """Test successful Jinja2 HTML rendering with report_template."""
    # Mock Jinja2 Template and Environment
    mock_template = mocker.MagicMock()
    mock_template.render.return_value = "<html><body><h1>Acme Report</h1></body></html>"

    mock_env = mocker.MagicMock()
    mock_env.get_template.return_value = mock_template

    # Patch Environment creation in html_generator
    mocker.patch(
        "crewai_custom_tools.reporting.html_generator.Environment",
        return_value=mock_env,
    )

    tool = RenderReportTool()
    result = tool._run(
        title="Acme Report",
        sections=[{"heading": "Section 1", "content": "Section 1 Content"}],
        citations=["http://acme.com"],
    )

    assert "Acme Report" in result
    mock_template.render.assert_called_once()


# ==============================================================================
# 2. PDF Generator and Specialized Template Tests
# ==============================================================================


def test_html_to_pdf_conversion_success(mocker):
    """Test that HtmlToPdfTool triggers WeasyPrint rendering upon valid inputs."""
    mocker.patch(
        "crewai_custom_tools.reporting.pdf_generator.WEASYPRINT_AVAILABLE", True
    )

    # Mock WeasyPrint HTML class and write_pdf
    mock_html_class = mocker.MagicMock()
    mocker.patch(
        "crewai_custom_tools.reporting.pdf_generator.HTML", return_value=mock_html_class
    )

    # Mock filesystem operations
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.makedirs")

    tool = HtmlToPdfTool()
    result = tool._run(
        html_file_path="/path/to/report.html", output_pdf_path="/path/to/output.pdf"
    )

    assert "Successfully converted" in result
    mock_html_class.write_pdf.assert_called_once_with("/path/to/output.pdf")


def test_pestel_report_renderer(mocker):
    """Test that PestelReportRenderer forces professional template rendering."""
    # Mock Jinja2 Template and Environment
    mock_template = mocker.MagicMock()
    mock_template.render.return_value = (
        "<html><body><h1>PESTEL Analysis</h1></body></html>"
    )

    mock_env = mocker.MagicMock()
    mock_env.get_template.return_value = mock_template

    mocker.patch(
        "crewai_custom_tools.reporting.html_generator.Environment",
        return_value=mock_env,
    )

    tool = PestelReportRenderer()
    result = tool._run(
        title="PESTEL Analysis",
        sections=[{"heading": "Political", "content": "Political stability"}],
    )

    assert "PESTEL Analysis" in result
    mock_env.get_template.assert_called_once_with("professional_report_template.html")


def test_financial_report_renderer(mocker):
    """Test that FinancialReportRenderer forces data template rendering."""
    # Mock Jinja2 Template and Environment
    mock_template = mocker.MagicMock()
    mock_template.render.return_value = (
        "<html><body><h1>Q2 Financial Report</h1></body></html>"
    )

    mock_env = mocker.MagicMock()
    mock_env.get_template.return_value = mock_template

    mocker.patch(
        "crewai_custom_tools.reporting.html_generator.Environment",
        return_value=mock_env,
    )

    tool = FinancialReportRenderer()
    result = tool._run(
        title="Q2 Financial Report",
        sections=[{"heading": "Revenue", "content": "10M USD"}],
    )

    assert "Q2 Financial Report" in result
    mock_env.get_template.assert_called_once_with("data_report_template.html")
