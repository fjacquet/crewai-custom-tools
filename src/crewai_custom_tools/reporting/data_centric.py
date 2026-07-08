"""Data-centric tools for metrics, KPIs, and structured data reporting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from crewai.tools import BaseTool

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models.data_metrics import (
    KPI,
    DataPoint,
    DataSeries,
    DataTable,
    Metric,
    MetricType,
    MetricValue,
    StructuredDataReport,
    TrendDirection,
)
from crewai_custom_tools.reporting.html_generator import build_environment


class MetricsCalculatorTool(BaseTool):
    """Create a typed metric and calculate its change/trend versus a previous value."""

    name: str = "metrics_calculator"
    description: str = (
        "Create a typed metric (numeric/percentage/currency/rating/…) and compute its change "
        "and trend versus an optional previous value. Returns the standardized metric object."
    )

    def _run(
        self,
        name: str,
        display_name: str,
        description: str,
        value: Any,
        type: str,
        previous_value: Any | None = None,
        unit: str | None = None,
        source: str | None = None,
        target: Any | None = None,
        is_key_metric: bool = False,
        **kwargs: Any,
    ) -> str:
        """Build a Metric with trend calculation and return it in the envelope."""
        try:
            metric = Metric(
                name=name,
                display_name=display_name,
                description=description,
                value=MetricValue(value=value, previous_value=previous_value),
                type=MetricType(type.lower()),
                unit=unit,
                source=source,
                target=target,
                is_key_metric=is_key_metric,
                timestamp=datetime.now(),
                metadata=kwargs.get("metadata", {}),
            )
            return ok(metric.model_dump())
        except Exception as exc:  # noqa: BLE001
            return err(f"Failed to calculate metric: {exc}")


class KPITrackerTool(BaseTool):
    """Create a KPI and calculate its progress toward a target and its status."""

    name: str = "kpi_tracker"
    description: str = (
        "Create a Key Performance Indicator with a target and compute progress-to-target and "
        "status (achieved/on track/needs attention/at risk). Returns the standardized KPI object."
    )

    def _run(
        self,
        name: str,
        display_name: str,
        description: str,
        value: Any,
        type: str,
        target: Any,
        previous_value: Any | None = None,
        unit: str | None = None,
        source: str | None = None,
        target_date: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build a KPI with progress/status calculation and return it in the envelope."""
        try:
            parsed_target_date = None
            if target_date:
                try:
                    parsed_target_date = datetime.fromisoformat(target_date)
                except ValueError:
                    parsed_target_date = None

            kpi = KPI(
                name=name,
                display_name=display_name,
                description=description,
                value=MetricValue(value=value, previous_value=previous_value),
                type=MetricType(type.lower()),
                unit=unit,
                source=source,
                target=target,
                target_date=parsed_target_date,
                progress_percentage=None,
                timestamp=datetime.now(),
                metadata=kwargs.get("metadata", {}),
            )
            return ok(kpi.model_dump())
        except Exception as exc:  # noqa: BLE001
            return err(f"Failed to track KPI: {exc}")


class DataVisualizationTool(BaseTool):
    """Format data into a standardized series or table structure for reporting."""

    name: str = "data_visualization"
    description: str = (
        "Format data into a standardized 'series' (labelled points) or 'table' (columns + rows) "
        "structure ready for visualization/reporting. Returns the standardized object."
    )

    def _run(self, type: str, name: str, **kwargs: Any) -> str:
        """Build a DataSeries or DataTable and return it in the envelope."""
        try:
            kind = type.lower()
            if kind == "series":
                points = [
                    DataPoint(
                        label=p.get("label", ""),
                        value=p.get("value"),
                        metadata=p.get("metadata", {}),
                    )
                    for p in kwargs.get("points", [])
                ]
                series = DataSeries(
                    name=name,
                    description=kwargs.get("description"),
                    points=points,
                    metadata=kwargs.get("metadata", {}),
                )
                return ok(series.model_dump())

            if kind == "table":
                table = DataTable(
                    name=name,
                    description=kwargs.get("description"),
                    columns=kwargs.get("columns", []),
                    rows=kwargs.get("rows", []),
                    metadata=kwargs.get("metadata", {}),
                )
                return ok(table.model_dump())

            return err(f"Unknown visualization type: {type!r} (expected 'series' or 'table')")
        except Exception as exc:  # noqa: BLE001
            return err(f"Failed to create data visualization: {exc}")


class StructuredReportTool(BaseTool):
    """Combine metrics, KPIs, series, and tables into one structured report (optional HTML)."""

    name: str = "structured_report"
    description: str = (
        "Combine metrics, KPIs, data series, and data tables into a single structured report. "
        "Pass generate_html=true to also render an HTML representation. Returns the report object."
    )

    def _run(self, title: str, description: str, **kwargs: Any) -> str:
        """Assemble a StructuredDataReport (optionally rendering HTML) and return the envelope."""
        try:
            metrics = [
                Metric(
                    name=m.get("name", ""),
                    display_name=m.get("display_name", ""),
                    description=m.get("description", ""),
                    value=MetricValue(
                        value=m.get("value", 0),
                        previous_value=m.get("previous_value"),
                        change_percentage=m.get("change_percentage"),
                        trend=m.get("trend", TrendDirection.UNKNOWN),
                    ),
                    type=m.get("type", MetricType.NUMERIC),
                    unit=m.get("unit"),
                    source=m.get("source"),
                    target=m.get("target"),
                    is_key_metric=m.get("is_key_metric", False),
                    timestamp=datetime.now(),
                    metadata=m.get("metadata", {}),
                )
                for m in kwargs.get("metrics", [])
            ]
            kpis = [
                KPI(
                    name=k.get("name", ""),
                    display_name=k.get("display_name", ""),
                    description=k.get("description", ""),
                    value=MetricValue(
                        value=k.get("value", 0),
                        previous_value=k.get("previous_value"),
                        change_percentage=k.get("change_percentage"),
                        trend=k.get("trend", TrendDirection.UNKNOWN),
                    ),
                    type=k.get("type", MetricType.NUMERIC),
                    unit=k.get("unit"),
                    source=k.get("source"),
                    target=k.get("target", 0),
                    target_date=k.get("target_date"),
                    progress_percentage=k.get("progress_percentage"),
                    status=k.get("status", "pending"),
                    timestamp=datetime.now(),
                    metadata=k.get("metadata", {}),
                )
                for k in kwargs.get("kpis", [])
            ]
            data_series = [
                DataSeries(
                    name=s.get("name", ""),
                    description=s.get("description"),
                    points=[
                        DataPoint(
                            label=p.get("label", ""),
                            value=p.get("value"),
                            metadata=p.get("metadata", {}),
                        )
                        for p in s.get("points", [])
                    ],
                    metadata=s.get("metadata", {}),
                )
                for s in kwargs.get("data_series", [])
            ]
            data_tables = [
                DataTable(
                    name=t.get("name", ""),
                    description=t.get("description"),
                    columns=t.get("columns", []),
                    rows=t.get("rows", []),
                    metadata=t.get("metadata", {}),
                )
                for t in kwargs.get("data_tables", [])
            ]

            report = StructuredDataReport(
                title=title,
                description=description,
                metrics=metrics,
                kpis=kpis,
                data_series=data_series,
                data_tables=data_tables,
                timestamp=datetime.now(),
                metadata=kwargs.get("metadata", {}),
                html=None,
            )

            if kwargs.get("generate_html", False):
                # Best-effort HTML: the structured data is returned regardless of render success.
                try:
                    template = build_environment().get_template("data_report_template.html")
                    report.html = template.render(
                        title=report.title,
                        description=report.description,
                        metrics=report.metrics,
                        kpis=report.kpis,
                        data_series=report.data_series,
                        data_tables=report.data_tables,
                        timestamp=report.timestamp,
                        metadata=report.metadata,
                    )
                except Exception:  # noqa: BLE001
                    report.html = None

            return ok(report.model_dump())
        except Exception as exc:  # noqa: BLE001
            return err(f"Failed to generate structured report: {exc}")
