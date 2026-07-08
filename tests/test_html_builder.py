"""Tests for the template-free HtmlGeneratorTool."""

import json

from crewai_custom_tools.reporting.html_builder import HtmlGeneratorTool


def _html(result):
    payload = json.loads(result)
    assert payload["success"] is True, payload
    return payload["data"]


def test_renders_all_block_types():
    blocks = [
        {"type": "heading", "text": "Overview", "level": 2},
        {"type": "paragraph", "text": "A summary paragraph."},
        {"type": "list", "items": ["one", "two"], "ordered": False},
        {"type": "table", "headers": ["A", "B"], "rows": [[1, 2], [3, 4]]},
        {"type": "code", "text": "print('hi')"},
    ]
    html = _html(HtmlGeneratorTool()._run(title="Report", blocks=blocks))
    assert "<h1>Report</h1>" in html
    assert "<h2>Overview</h2>" in html
    assert "<p>A summary paragraph.</p>" in html
    assert "<li>one</li>" in html
    assert "<th>A</th>" in html and "<td>1</td>" in html
    assert "<pre><code>print(" in html
    assert "<body>" in html  # complete document


def test_escapes_untrusted_content():
    blocks = [{"type": "paragraph", "text": "<script>alert('xss')</script>"}]
    html = _html(HtmlGeneratorTool()._run(title="<script>t</script>", blocks=blocks))
    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;" in html


def test_unknown_block_type_errors():
    payload = json.loads(
        HtmlGeneratorTool()._run(title="T", blocks=[{"type": "bogus", "text": "x"}])
    )
    assert payload["success"] is False
    assert "Unknown block type" in payload["error"]
