"""Tests for output formatting."""

import tempfile
from pathlib import Path

import pytest

from codesnap.config import Language
from codesnap.formatters import SnapshotFormatter


@pytest.fixture
def temp_project():
    """Create a temporary project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_format_header(temp_project):
    """Test header formatting."""
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)
    header = formatter.format_header()

    assert f"# Project: {temp_project.name}" in header
    assert "Language: python" in header
    assert str(temp_project) in header


def test_format_tree():
    """Test tree formatting."""
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)

    tree = {
        "name": "project",
        "type": "directory",
        "children": [
            {"name": "src", "type": "directory", "children": [
                {"name": "main.py", "type": "file", "children": None}
            ]},
            {"name": "README.md", "type": "file", "children": None}
        ]
    }

    result = formatter.format_tree(tree)

    assert "## Directory Structure" in result
    assert "project/" in result
    assert "├── src/" in result
    assert "│   └── main.py" in result
    assert "└── README.md" in result


def test_format_file(temp_project):
    """Test file content formatting."""
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)

    # Create a test file
    test_file = temp_project / "test.py"
    test_file.write_text("def hello():\n    print('Hello')\n")

    result = formatter.format_file(test_file)

    assert "### test.py" in result
    assert "```python" in result
    assert "def hello():" in result
    assert "print('Hello')" in result


def test_format_file_with_line_limit(temp_project):
    """Test file formatting with line limit."""
    formatter = SnapshotFormatter(temp_project, Language.PYTHON)

    # Create a file with many lines
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
    """Test footer formatting."""
    formatter = SnapshotFormatter(Path("/test"), Language.PYTHON)
    footer = formatter.format_footer(10, 1500)

    assert "Total files: 10" in footer
    assert "Approximate tokens: 1,500" in footer


def test_language_detection_for_syntax():
    """Test language detection for syntax highlighting."""
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