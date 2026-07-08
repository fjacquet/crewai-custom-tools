"""Tests for the Phase 2f-1 reporting + data-centric tools."""

import json

from crewai_custom_tools.reporting.data_centric import (
    DataVisualizationTool,
    KPITrackerTool,
    MetricsCalculatorTool,
    StructuredReportTool,
)
from crewai_custom_tools.reporting.report_writers import ReportingTool, UniversalReportTool


def _payload(result: str) -> dict:
    payload = json.loads(result)
    assert set(payload) == {"success", "data", "error"}
    return payload


# --- data-centric tools ---------------------------------------------------


def test_metrics_calculator_computes_trend():
    payload = _payload(
        MetricsCalculatorTool()._run(
            name="rev", display_name="Revenue", description="Quarterly revenue",
            value=110, previous_value=100, type="currency",
        )
    )
    assert payload["success"] is True
    mv = payload["data"]["value"]
    assert round(mv["change_percentage"]) == 10
    assert mv["trend"] == "up"


def test_metrics_calculator_bad_type_errors():
    payload = _payload(
        MetricsCalculatorTool()._run(
            name="x", display_name="X", description="d", value=1, type="not-a-type",
        )
    )
    assert payload["success"] is False


def test_kpi_tracker_progress_and_status():
    payload = _payload(
        KPITrackerTool()._run(
            name="signups", display_name="Signups", description="new users",
            value=80, type="count", target=100,
        )
    )
    assert payload["success"] is True
    assert round(payload["data"]["progress_percentage"]) == 80
    assert payload["data"]["status"] == "on track"


def test_data_visualization_series_table_and_unknown():
    series = _payload(
        DataVisualizationTool()._run(
            type="series", name="s", points=[{"label": "Jan", "value": 1}]
        )
    )
    assert series["success"] is True
    assert series["data"]["points"][0]["label"] == "Jan"

    table = _payload(
        DataVisualizationTool()._run(
            type="table", name="t", columns=["a"], rows=[[1], [2]]
        )
    )
    assert table["success"] is True
    assert table["data"]["rows"] == [[1], [2]]

    bad = _payload(DataVisualizationTool()._run(type="pie", name="p"))
    assert bad["success"] is False


def test_structured_report_combines_and_renders_html():
    payload = _payload(
        StructuredReportTool()._run(
            title="Q2", description="quarter",
            metrics=[{"name": "rev", "display_name": "Revenue", "value": 10, "type": "currency"}],
            generate_html=True,
        )
    )
    assert payload["success"] is True
    assert payload["data"]["title"] == "Q2"
    assert len(payload["data"]["metrics"]) == 1
    assert payload["data"]["html"] and "Q2" in payload["data"]["html"]


# --- report writers -------------------------------------------------------


def test_reporting_tool_writes_file(tmp_path):
    out = tmp_path / "sub" / "report.html"
    payload = _payload(
        ReportingTool()._run(
            report_title="My Report",
            report_body="<p>Body <b>content</b></p>",
            output_file_path=str(out),
        )
    )
    assert payload["success"] is True
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "My Report" in html
    # Trusted HTML body is inserted as markup (bold tag preserved).
    assert "<b>content</b>" in html


def test_universal_report_returns_html_and_preserves_trusted_body():
    payload = _payload(
        UniversalReportTool()._run(title="Doc", content="<ul><li>one</li></ul>")
    )
    assert payload["success"] is True
    html = payload["data"]
    assert "Doc" in html
    assert "<ul><li>one</li></ul>" in html  # trusted HTML preserved


def test_universal_report_escapes_untrusted_title():
    """Title is plain text → autoescaped (the HTML *body* is the only trusted slot)."""
    payload = _payload(
        UniversalReportTool()._run(title="<script>alert(1)</script>", content="<p>ok</p>")
    )
    html = payload["data"]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
