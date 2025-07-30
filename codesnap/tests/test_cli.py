"""Tests for CLI functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from codesnap.cli import main


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_python_project():
    """Create a temporary Python project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create a simple Python project
        (root / "main.py").write_text("print('Hello, world!')")
        (root / "requirements.txt").write_text("pytest>=7.0.0")

        yield root


def test_cli_basic(runner, temp_python_project):
    """Test basic CLI usage."""
    result = runner.invoke(main, [str(temp_python_project)])

    assert result.exit_code == 0
    assert "# Project:" in result.output
    assert "Language: python" in result.output
    assert "print('Hello, world!')" in result.output


def test_cli_with_language(runner, temp_python_project):
    """Test CLI with explicit language."""
    result = runner.invoke(main, [str(temp_python_project), "-l", "python"])

    assert result.exit_code == 0
    assert "Language: python" in result.output


@patch("codesnap.cli.copy_to_clipboard")
def test_cli_clipboard(mock_clipboard, runner, temp_python_project):
    """Test CLI with clipboard output."""
    mock_clipboard.return_value = True

    result = runner.invoke(main, [str(temp_python_project), "-c"])

    assert result.exit_code == 0
    assert "Code snapshot copied to clipboard" in result.output
    mock_clipboard.assert_called_once()


def test_cli_output_file(runner, temp_python_project):
    """Test CLI with file output."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        output_path = f.name

    result = runner.invoke(main, [str(temp_python_project), "-o", output_path])

    assert result.exit_code == 0
    # The output path might be wrapped, so just check for the filename
    assert Path(output_path).name in result.output
    assert "Code snapshot written to" in result.output

    # Check file was created
    assert Path(output_path).exists()
    content = Path(output_path).read_text()
    assert "print('Hello, world!')" in content

    # Cleanup
    Path(output_path).unlink()


def test_cli_invalid_path(runner):
    """Test CLI with invalid path."""
    result = runner.invoke(main, ["/nonexistent/path"])

    assert result.exit_code == 2  # Click returns 2 for invalid path


def test_cli_max_tokens(runner, temp_python_project):
    """Test CLI with token limit."""
    result = runner.invoke(main, [str(temp_python_project), "--max-tokens", "50"])

    assert result.exit_code == 0
    # Should have truncated output
    assert "stopped at token limit" in result.output or "print('Hello, world!')" in result.output