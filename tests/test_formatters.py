"""Tests for output formatting."""

import tempfile
import pytest
import os
from unittest.mock import patch
from pathlib import Path

from codesnap.config import Language
from codesnap.formatters import SnapshotFormatter, OutputFormat


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_format_header(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    header = formatter.format_header()
    assert f"# Project: {temp_project.name}" in header
    assert "Language: python" in header
    assert str(temp_project) in header


def test_format_tree():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    tree = {
        "name": "project",
        "type": "directory",
        "children": [
            {
                "name": "src",
                "type": "directory",
                "children": [{"name": "main.py", "type": "file", "children": None}],
            },
            {"name": "README.md", "type": "file", "children": None},
        ],
    }
    result = formatter.format_tree(tree)
    assert "## Directory Structure" in result
    assert "project/" in result
    assert "├── src/" in result
    assert "│   └── main.py" in result
    assert "└── README.md" in result


def test_format_file(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    test_file = temp_project / "test.py"
    test_file.write_text("def hello():\n    print('Hello')\n")
    result = formatter.format_file(test_file)
    assert "### test.py" in result
    assert "```python" in result
    assert "def hello():" in result
    assert "print('Hello')" in result


def test_format_file_with_line_limit(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    test_file = temp_project / "long.py"
    content = "\n".join(f"line {i}" for i in range(100))
    test_file.write_text(content)
    result = formatter.format_file(test_file, max_lines=10)
    assert "line 0" in result
    assert "line 9" in result
    assert "line 10" not in result
    assert "truncated" in result
    assert "90 more lines" in result


def test_format_footer():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    footer = formatter.format_footer(10, 1500)
    assert "Total files: 10" in footer
    assert "Approximate tokens: 1,500" in footer


def test_language_detection_for_syntax():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    test_cases = [
        ("test.py", "python"),
        ("test.js", "javascript"),
        ("test.ts", "typescript"),
        ("test.jsx", "jsx"),
        ("test.json", "json"),
        ("Dockerfile", "dockerfile"),
        (".gitignore", "gitignore"),
    ]
    for filename, expected_lang in test_cases:
        lang = formatter._get_language_ext(Path(filename))
        assert lang == expected_lang, f"Failed for {filename}: expected {expected_lang}, got {lang}"


def test_binary_file_handling(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    binary_file = temp_project / "image.png"
    with open(binary_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    result = formatter.format_file(binary_file)
    assert "### image.png" in result
    assert "Binary file (not shown)" in result
    assert "```" not in result  # Should not have code formatting


def test_files_with_special_characters(temp_project):
    special_file = temp_project / "special-chars-!@#$.py"
    special_file.write_text("print('special')")
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    result = formatter.format_file(special_file)
    assert "### special-chars-!@#$.py" in result
    assert "print('special')" in result


def test_non_utf8_encoding(temp_project):
    latin1_file = temp_project / "latin1.py"
    with open(latin1_file, "wb") as f:
        f.write("# -*- coding: latin-1 -*-\nprint('Café')".encode("latin-1"))
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    result = formatter.format_file(latin1_file)
    assert "### latin1.py" in result
    assert "Binary file (not shown)" in result


def test_very_long_filenames(temp_project):
    if os.name == "nt":
        pytest.skip("Windows has shorter filename limits")
    long_name = "a" * 240 + ".py"
    long_file = temp_project / long_name
    long_file.write_text("print('long')")
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    result = formatter.format_file(long_file)
    assert long_name in result
    assert "print('long')" in result


def test_format_file_with_very_long_lines(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    long_line_file = temp_project / "long_line.py"
    long_line_file.write_text("x = '" + "a" * 10000 + "'")
    result = formatter.format_file(long_line_file)
    assert "### long_line.py" in result
    assert "x = '" in result
    assert "'" in result  # End of the string should be there


def test_format_file_with_unusual_extensions(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    unusual_file = temp_project / "unusual.xyz"
    unusual_file.write_text("This is an unusual file type")
    result = formatter.format_file(unusual_file)
    assert "### unusual.xyz" in result
    assert "```xyz" in result
    assert "This is an unusual file type" in result


def test_format_file_with_permission_error(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    test_file = temp_project / "test.py"
    test_file.write_text("print('test')")
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        result = formatter.format_file(test_file)
        assert "### test.py" in result
        assert "Error reading file: Permission denied" in result


def test_format_tree_with_empty_tree():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    tree = {"name": "empty", "type": "directory", "children": []}
    result = formatter.format_tree(tree)
    assert "## Directory Structure" in result
    assert "empty/" in result
    assert len(result.splitlines()) == 4  # Header, tree start, root, tree end


def test_format_header_with_special_chars():
    path = Path("/test with spaces/and#special&chars")
    formatter = SnapshotFormatter(path, Language.PYTHON)
    header = formatter.format_header()
    assert "# Project: and#special&chars" in header
    assert "Language: python" in header
    assert str(path) in header


def test_set_output_format():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    assert formatter.output_format == OutputFormat.MARKDOWN
    formatter.set_output_format(OutputFormat.TEXT)
    assert formatter.output_format == OutputFormat.TEXT
    formatter.set_output_format(OutputFormat.JSON)
    assert formatter.output_format == OutputFormat.JSON


def test_format_header_with_different_formats():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    formatter.set_output_format(OutputFormat.MARKDOWN)
    header = formatter.format_header()
    assert header.startswith("# Project:")
    formatter.set_output_format(OutputFormat.TEXT)
    header = formatter.format_header()
    assert header.startswith("Project:")
    assert "#" not in header
    formatter.set_output_format(OutputFormat.JSON)
    header = formatter.format_header()
    assert header == ""


def test_format_tree_with_different_formats():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    tree = {
        "name": "project",
        "type": "directory",
        "children": [{"name": "file.py", "type": "file", "children": None}],
    }
    formatter.set_output_format(OutputFormat.MARKDOWN)
    result = formatter.format_tree(tree)
    assert "## Directory Structure" in result
    assert "```" in result
    formatter.set_output_format(OutputFormat.TEXT)
    result = formatter.format_tree(tree)
    assert "Directory Structure:" in result
    assert "```" not in result
    formatter.set_output_format(OutputFormat.JSON)
    result = formatter.format_tree(tree)
    assert result == ""


def test_format_tree_with_max_depth():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    tree = {
        "name": "project",
        "type": "directory",
        "children": [
            {
                "name": "level1",
                "type": "directory",
                "children": [
                    {
                        "name": "level2",
                        "type": "directory",
                        "children": [{"name": "deep.py", "type": "file", "children": None}],
                    }
                ],
            }
        ],
    }
    result = formatter.format_tree(tree)
    assert "deep.py" in result
    result = formatter.format_tree(tree, max_depth=1)
    assert "level1/" in result
    assert "..." in result
    assert "level2" not in result
    assert "deep.py" not in result


def test_format_tree_with_different_styles():
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    tree = {
        "name": "project",
        "type": "directory",
        "children": [{"name": "file.py", "type": "file", "children": None}],
    }
    unicode_result = formatter.format_tree(tree, style="unicode")
    assert "├──" in unicode_result or "└──" in unicode_result
    ascii_result = formatter.format_tree(tree, style="ascii")
    assert "|--" in ascii_result or "`--" in ascii_result


def test_format_file_with_different_formats():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        test_file = root / "test.py"
        test_file.write_text("print('test')")
        formatter = SnapshotFormatter(root, Language.PYTHON)
        formatter.set_output_format(OutputFormat.MARKDOWN)
        result = formatter.format_file(test_file)
        assert "### test.py" in result
        assert "```python" in result
        formatter.set_output_format(OutputFormat.TEXT)
        result = formatter.format_file(test_file)
        assert "File: test.py" in result
        assert "```" not in result
        formatter.set_output_format(OutputFormat.JSON)
        result = formatter.format_file(test_file)
        assert result == ""


def test_format_file_with_max_line_length(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    long_line_file = temp_project / "long_line.py"
    long_line_text = "print('this is a very long line that exceeds the maximum allowed length')"
    long_line_file.write_text(long_line_text)
    result = formatter.format_file(long_line_file, max_line_length=30)
    assert "### long_line.py" in result
    assert "print('this is a ver" in result
    assert "(43 more chars)" in result  # Updated to match actual character count


def test_format_file_with_mixed_line_limits(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    mixed_file = temp_project / "mixed_lines.py"
    mixed_content = "\n".join(
        [
            "def short_func():",
            "    print('short line')",
            "    print('this is a very long line that exceeds the maximum allowed length')",
            "    return True",
        ]
    )
    mixed_file.write_text(mixed_content)
    result = formatter.format_file(mixed_file, max_lines=2, max_line_length=30)
    assert "### mixed_lines.py" in result
    assert "def short_func():" in result
    assert "print('short line')" in result
    assert "(truncated, 2 more lines)" in result


def test_format_file_with_unicode_content(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    unicode_file = temp_project / "unicode.py"
    unicode_content = "def hello_world():\n    print('こんにちは、世界！ Hello, World! 🌍')"
    unicode_file.write_text(unicode_content)
    result = formatter.format_file(unicode_file)
    assert "こんにちは、世界！ Hello, World! 🌍" in result


def test_format_file_with_special_characters(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    special_file = temp_project / "special_chars.py"
    special_content = (
        "def test_special_chars():\n"
        "    # Various escape sequences and special characters\n"
        "    print('\\t Tab \\n Newline \\r Return \" Quote \\' Single Quote')\n"
        "    regex_pattern = r'[A-Za-z0-9_\\-]+'\n"
    )
    special_file.write_text(special_content)
    result = formatter.format_file(special_file)
    assert "\\t Tab \\n Newline \\r Return \" Quote \\' Single Quote" in result
    assert "[A-Za-z0-9_\\-]+" in result


def test_format_file_with_empty_file(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    empty_file = temp_project / "empty.py"
    empty_file.write_text("")
    result = formatter.format_file(empty_file)
    assert "### empty.py" in result
    assert "```python" in result
    assert "```" in result


def test_format_file_with_error_reading_file(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    test_file = temp_project / "test.py"
    test_file.write_text("print('test')")
    with patch("builtins.open", side_effect=Exception("Generic error")):
        result = formatter.format_file(test_file)
        assert "### test.py" in result
        assert "Error reading file: Generic error" in result


def test_format_file_with_line_limit_and_empty_file(temp_project):
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    empty_file = temp_project / "empty.py"
    empty_file.write_text("")
    result = formatter.format_file(empty_file, max_lines=10)
    assert "### empty.py" in result
    assert "```python" in result
    assert "```" in result
    assert "truncated" not in result


def test_format_tree_json_format(tmp_path):
    formatter = SnapshotFormatter(tmp_path, Language.PYTHON)
    formatter.set_output_format(OutputFormat.JSON)
    tree = {"name": "foo", "type": "directory", "children": []}
    assert formatter.format_tree(tree) == ""


def test_format_file_binary_file(tmp_path):
    f = tmp_path / "b.bin"
    f.write_bytes(b"\x89PNG\x01\x00")
    formatter = SnapshotFormatter(tmp_path, Language.PYTHON)
    out = formatter.format_file(f)
    assert "Binary file" in out


def test_format_file_handles_exception_open(monkeypatch, tmp_path):
    f = tmp_path / "err.py"
    f.write_text("1")
    formatter = SnapshotFormatter(tmp_path, Language.PYTHON)

    def broken(*a, **k):
        raise Exception("x")

    monkeypatch.setattr("builtins.open", broken)
    out = formatter.format_file(f)
    assert "Error reading file:" in out


def test_format_file_permission_error(monkeypatch, tmp_path):
    f = tmp_path / "no_access.py"
    f.write_text("print('x')")
    formatter = SnapshotFormatter(tmp_path, Language.PYTHON)

    def broken(*a, **k):
        raise PermissionError("perm")

    monkeypatch.setattr("builtins.open", broken)
    assert "Error reading file: perm" in formatter.format_file(f)
