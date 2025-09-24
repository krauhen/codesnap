"""Tests for CLI functionality with simplified codesnap.cli."""
import tempfile
from pathlib import Path
import pytest
from click.testing import CliRunner
from codesnap.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_python_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "main.py").write_text("print('Hello, world!')")
        (root / "requirements.txt").write_text("pytest>=7.0.0")
        yield root


def test_cli_basic(runner, temp_python_project):
    """Basic CLI run should succeed and include header & file contents."""
    result = runner.invoke(main, [str(temp_python_project), "-l", "python"])
    assert result.exit_code == 0
    # In new implementation default header is plain text ("Project:")
    assert "Project:" in result.output
    assert "Language: python" in result.output
    assert "print('Hello, world!')" in result.output


def test_cli_with_language(runner, temp_python_project):
    result = runner.invoke(main, [str(temp_python_project), "-l", "python"])
    assert result.exit_code == 0
    assert "Language: python" in result.output


def test_cli_clipboard(monkeypatch, runner, temp_python_project):
    monkeypatch.setattr("codesnap.cli.copy_to_clipboard", lambda txt: True)
    result = runner.invoke(main, [str(temp_python_project), "-l", "python", "-c"])
    assert result.exit_code == 0
    assert "Snapshot copied to clipboard" in result.output


def test_cli_clipboard_failure(monkeypatch, runner, temp_python_project):
    monkeypatch.setattr("codesnap.cli.copy_to_clipboard", lambda txt: False)
    result = runner.invoke(main, [str(temp_python_project), "-l", "python", "-c"])
    assert result.exit_code == 1
    assert "Clipboard copy failed" in result.output


def test_cli_output_file(runner, temp_python_project, tmp_path):
    output_file = tmp_path / "snapshot.txt"
    result = runner.invoke(
        main, [str(temp_python_project), "-l", "python", "-o", str(output_file)]
    )
    assert result.exit_code == 0
    assert "Snapshot written to" in result.output
    assert output_file.exists()
    text = output_file.read_text()
    assert "print('Hello, world!')" in text


def test_cli_invalid_path(runner):
    """Click will error on non-existent path."""
    result = runner.invoke(main, ["/does/not/exist"])
    assert result.exit_code == 2


def test_cli_language_detection_failure(runner, tmp_path, monkeypatch):
    monkeypatch.setattr("codesnap.cli.detect_language", lambda p: None)
    result = runner.invoke(main, [str(tmp_path)])
    assert result.exit_code == 1
    assert "Could not detect language" in result.output


def test_cli_model_encoding_option(runner, temp_python_project):
    result = runner.invoke(
        main, [str(temp_python_project), "-l", "python", "--model-encoding", "cl100k_base"]
    )
    assert result.exit_code == 0


def test_cli_max_tokens(runner, temp_python_project):
    result = runner.invoke(main, [str(temp_python_project), "-l", "python", "--max-tokens", "50"])
    assert result.exit_code == 0


def test_cli_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    # Ensure our help text header is there
    assert "Generate an LLM-friendly snapshot" in result.output


def test_cli_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0