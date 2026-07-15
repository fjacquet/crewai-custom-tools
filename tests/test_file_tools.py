"""Tests for the ported FileReadTool/DirectoryReadTool (tools/files).

Unlike the rest of the suite, these tools return plain strings rather than
the ok()/err() envelope, so assertions here compare against the exact
string family the tools produce (including the "Error: ..." messages),
not against a parsed JSON payload.
"""

import os

import pytest

from crewai_custom_tools.tools.files.file_tools import (
    DirectoryReadTool,
    DirectoryReadToolSchema,
    FileReadTool,
    FixedDirectoryReadToolSchema,
)

_RUNNING_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


# --- FileReadTool --------------------------------------------------------


def test_file_read_full_content(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("line1\nline2\nline3\n")

    assert FileReadTool()._run(file_path=str(target)) == "line1\nline2\nline3\n"


def test_file_read_line_range(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("line1\nline2\nline3\nline4\n")

    result = FileReadTool()._run(file_path=str(target), start_line=2, line_count=2)

    assert result == "line2\nline3\n"


def test_file_read_start_line_past_eof(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("line1\nline2\n")

    result = FileReadTool()._run(file_path=str(target), start_line=10)

    assert result == "Error: Start line 10 exceeds the number of lines in the file."


def test_file_read_missing_file(tmp_path):
    missing = tmp_path / "nope.txt"

    result = FileReadTool()._run(file_path=str(missing))

    assert result == f"Error: File not found at path: {missing}"


def test_file_read_no_path_provided():
    result = FileReadTool()._run()

    assert result == (
        "Error: No file path provided. Please provide a file path either in the constructor or as an argument."
    )


@pytest.mark.skipif(_RUNNING_AS_ROOT, reason="root bypasses filesystem permission checks")
def test_file_read_permission_denied(tmp_path):
    target = tmp_path / "locked.txt"
    target.write_text("secret")
    target.chmod(0o000)
    try:
        result = FileReadTool()._run(file_path=str(target))
        assert result == f"Error: Permission denied when trying to read file: {target}"
    finally:
        target.chmod(0o644)


def test_file_read_constructor_fixed_path(tmp_path):
    target = tmp_path / "fixed.txt"
    target.write_text("fixed content")

    tool = FileReadTool(file_path=str(target))

    assert tool._run() == "fixed content"
    assert str(target) in tool.description


def test_file_read_runtime_override(tmp_path):
    fixed = tmp_path / "fixed.txt"
    fixed.write_text("fixed content")
    other = tmp_path / "other.txt"
    other.write_text("other content")

    tool = FileReadTool(file_path=str(fixed))
    result = tool._run(file_path=str(other))

    assert result == "other content"


# --- DirectoryReadTool -----------------------------------------------------


def test_directory_read_lists_files_recursively(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("b")

    result = DirectoryReadTool()._run(directory=str(tmp_path))

    assert result.startswith("File paths: \n-")
    assert f"{tmp_path}/a.txt" in result
    assert f"{tmp_path}/sub/b.txt" in result


def test_directory_read_strips_trailing_slash(tmp_path):
    (tmp_path / "a.txt").write_text("a")

    result = DirectoryReadTool()._run(directory=f"{tmp_path}/")

    assert f"{tmp_path}/a.txt" in result


def test_directory_read_missing_directory_raises():
    with pytest.raises(ValueError, match="Directory must be provided."):
        DirectoryReadTool()._run()


def test_directory_read_fixed_directory_schema_swap(tmp_path):
    tool = DirectoryReadTool(directory=str(tmp_path))

    assert tool.args_schema is FixedDirectoryReadToolSchema
    assert str(tmp_path) in tool.description


def test_directory_read_runtime_directory_keeps_default_schema():
    tool = DirectoryReadTool()

    assert tool.args_schema is DirectoryReadToolSchema


def test_directory_read_fixed_directory_used_when_no_override(tmp_path):
    (tmp_path / "a.txt").write_text("a")

    tool = DirectoryReadTool(directory=str(tmp_path))
    result = tool._run()

    assert f"{tmp_path}/a.txt" in result


def test_directory_read_runtime_override(tmp_path):
    fixed = tmp_path / "fixed"
    fixed.mkdir()
    (fixed / "f.txt").write_text("f")
    other = tmp_path / "other"
    other.mkdir()
    (other / "o.txt").write_text("o")

    tool = DirectoryReadTool(directory=str(fixed))
    result = tool._run(directory=str(other))

    assert f"{other}/o.txt" in result
    assert "f.txt" not in result
