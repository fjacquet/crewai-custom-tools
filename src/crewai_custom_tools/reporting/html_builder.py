"""Template-free programmatic HTML document generator.

Distinct from ``RenderReportTool``: that one renders a Jinja *template file* with a
fixed context; this one builds a complete, self-styled HTML document from a list of
typed content blocks — no template needed. All caller-supplied text is escaped, so
untrusted content cannot inject markup.
"""

from crewai.tools import BaseTool
from markupsafe import escape
from pydantic import BaseModel, Field

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.reporting.html_generator import validate_html

_STYLE = (
    "body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:60rem;"
    "margin:2rem auto;padding:0 1rem;color:#1a1a1a;line-height:1.6}"
    "table{border-collapse:collapse;width:100%;margin:1rem 0}"
    "th,td{border:1px solid #ddd;padding:.5rem .75rem;text-align:left}"
    "th{background:#f5f5f5}code,pre{background:#f5f5f5;border-radius:4px}"
    "pre{padding:1rem;overflow-x:auto}"
)


def _heading(block: dict) -> str:
    level = block.get("level", 2)
    level = level if isinstance(level, int) and 1 <= level <= 6 else 2
    return f"<h{level}>{escape(str(block.get('text', '')))}</h{level}>"


def _paragraph(block: dict) -> str:
    return f"<p>{escape(str(block.get('text', '')))}</p>"


def _list(block: dict) -> str:
    tag = "ol" if block.get("ordered") else "ul"
    items = "".join(f"<li>{escape(str(i))}</li>" for i in block.get("items", []))
    return f"<{tag}>{items}</{tag}>"


def _table(block: dict) -> str:
    headers = "".join(f"<th>{escape(str(h))}</th>" for h in block.get("headers", []))
    rows = "".join(
        "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row) + "</tr>"
        for row in block.get("rows", [])
    )
    thead = f"<thead><tr>{headers}</tr></thead>" if headers else ""
    return f"<table>{thead}<tbody>{rows}</tbody></table>"


def _code(block: dict) -> str:
    return f"<pre><code>{escape(str(block.get('text', '')))}</code></pre>"


_RENDERERS = {
    "heading": _heading,
    "paragraph": _paragraph,
    "list": _list,
    "table": _table,
    "code": _code,
}


class HtmlGeneratorInput(BaseModel):
    """Input schema for HtmlGeneratorTool."""

    title: str = Field(..., description="Document title (also the <h1>).")
    blocks: list[dict] = Field(
        ...,
        description=(
            "Ordered content blocks. Each is a dict with 'type' in "
            "{heading, paragraph, list, table, code} plus its payload — e.g. "
            "heading:{text,level}, paragraph:{text}, list:{items,ordered}, "
            "table:{headers,rows}, code:{text}."
        ),
    )


class HtmlGeneratorTool(BaseTool):
    """Build a complete, self-styled HTML document from typed content blocks (no template)."""

    name: str = "html_generator"
    description: str = (
        "Generate a complete standalone HTML document programmatically from a title and "
        "a list of typed blocks (heading, paragraph, list, table, code) — no template "
        "file required. All text is escaped against injection."
    )
    args_schema: type[BaseModel] = HtmlGeneratorInput

    def _run(self, title: str, blocks: list[dict]) -> str:
        """Render the blocks into a full HTML document."""
        body_parts = [f"<h1>{escape(str(title))}</h1>"]
        for block in blocks or []:
            renderer = _RENDERERS.get(str(block.get("type", "")).lower())
            if renderer is None:
                return err(
                    f"Unknown block type {block.get('type')!r}; "
                    f"expected one of {sorted(_RENDERERS)}."
                )
            body_parts.append(renderer(block))

        html = (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{escape(str(title))}</title><style>{_STYLE}</style></head>"
            f"<body>{''.join(body_parts)}</body></html>"
        )
        validate_html(html, raise_on_error=True)
        return ok(html)
