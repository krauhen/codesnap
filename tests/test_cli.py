"""Tests for CLI functionality."""

import sys
import tempfile
import pytest

from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from codesnap.cli import main, nullcontext


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
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
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


@patch("codesnap.cli.detect_language", return_value=None)
def test_cli_language_detection_failure(mock_detect, runner, temp_python_project):
    """Test CLI behavior when language detection fails."""
    result = runner.invoke(main, [str(temp_python_project)])

    assert result.exit_code == 1
    assert "Could not auto-detect language" in result.output


@patch("codesnap.cli.copy_to_clipboard", return_value=False)
def test_cli_clipboard_failure(mock_clipboard, runner, temp_python_project):
    """Test CLI behavior when clipboard copy fails."""
    result = runner.invoke(main, [str(temp_python_project), "-c"])

    assert result.exit_code == 1
    assert "Failed to copy to clipboard" in result.output


@patch("codesnap.cli.CodeSnapshotter")
def test_cli_general_error(mock_snapshotter, runner, temp_python_project):
    """Test CLI behavior when an unexpected error occurs."""
    # Simulate an error in the snapshotter
    mock_snapshotter.side_effect = Exception("Test error")

    result = runner.invoke(main, [str(temp_python_project)])

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Test error" in result.output


def test_cli_model_encoding_option(runner, temp_python_project):
    """Test CLI with model encoding option."""
    result = runner.invoke(main, [str(temp_python_project), "--model-encoding", "cl100k_base"])

    assert result.exit_code == 0
    assert "Language: python" in result.output


def test_cli_multiple_search_terms(runner, temp_python_project):
    """Test CLI with multiple search terms."""
    # Create test files
    (temp_python_project / "search_this.py").write_text("print('found')")
    (temp_python_project / "also_search.py").write_text("print('also found')")
    (temp_python_project / "ignore_this.py").write_text("print('ignored')")

    result = runner.invoke(main, [str(temp_python_project), "-s", "search", "-s", "also"])

    assert result.exit_code == 0
    assert "search_this.py" in result.output
    assert "also_search.py" in result.output
    assert "ignore_this.py" not in result.output


def test_cli_with_profile(runner, temp_python_project):
    """Test CLI with profile loading."""
    # Create a config file with a profile
    config_path = temp_python_project / "codesnap.json"
    config_path.write_text("""
    {
        "profiles": {
            "test_profile": {
                "ignore": ["*.log"],
                "max_file_lines": 50
            }
        }
    }
    """)

    result = runner.invoke(
        main,
        [str(temp_python_project), "--profile", "test_profile", "--config-file", str(config_path)],
    )
    assert result.exit_code == 0
    assert "Loaded profile: test_profile" in result.output


def test_cli_with_save_profile(runner, temp_python_project):
    """Test CLI with profile saving."""
    config_path = temp_python_project / "codesnap.json"

    # Create an empty config file first
    config_path.write_text("{}")

    # Run the command
    result = runner.invoke(
        main,
        [
            str(temp_python_project),
            "--save-profile",
            "new_profile",
            "--config-file",
            str(config_path),
            "--max-file-lines",
            "25",
            "-v",  # Add verbose flag to see the confirmation message
        ],
    )

    # Print debug information
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")
    if result.exception:
        print(f"Exception: {result.exception}")

    # Verify the profile was saved
    import json

    config_data = json.loads(config_path.read_text())
    assert "profiles" in config_data
    assert "new_profile" in config_data["profiles"]
    assert config_data["profiles"]["new_profile"]["max_file_lines"] == 25

    # Check for the message in verbose mode
    assert "Saved profile: new_profile" in result.output


def test_cli_with_nonexistent_profile(runner, temp_python_project):
    """Test CLI with non-existent profile."""
    config_path = temp_python_project / "codesnap.json"
    config_path.write_text('{"profiles": {}}')

    result = runner.invoke(
        main,
        [str(temp_python_project), "--profile", "nonexistent", "--config-file", str(config_path)],
    )
    assert result.exit_code == 0
    assert "Warning: Profile 'nonexistent' not found" in result.output


def test_cli_with_tree_options(runner, temp_python_project):
    """Test CLI with tree display options."""
    # Test with no tree
    result = runner.invoke(main, [str(temp_python_project), "--no-tree"])
    assert result.exit_code == 0
    assert "Directory Structure" not in result.output

    # Test with tree depth
    result = runner.invoke(main, [str(temp_python_project), "--tree-depth", "1"])
    assert result.exit_code == 0
    assert "Directory Structure" in result.output

    # Test with ASCII tree style
    result = runner.invoke(main, [str(temp_python_project), "--tree-style", "ascii"])
    assert result.exit_code == 0
    assert "|--" in result.output or "`--" in result.output


def test_cli_quiet_mode(runner, temp_python_project):
    """Test CLI in quiet mode."""
    result = runner.invoke(main, [str(temp_python_project), "-q"])
    assert result.exit_code == 0
    # Should only contain the actual output, not status messages
    assert "Generating code snapshot" not in result.output
    assert "# Project:" in result.output


def test_cli_verbose_mode(runner, temp_python_project):
    """Test CLI in verbose mode."""
    result = runner.invoke(main, [str(temp_python_project), "-v"])
    assert result.exit_code == 0
    # Should include additional info
    assert "Auto-detected language" in result.output


def test_nullcontext_context_manager():
    nc = nullcontext()
    with nc as val:
        assert val is None


def test_main_clipboard_output(tmp_path, monkeypatch):
    # Change to use temp directory to avoid file system pollution
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "main.py").write_text("print('foo')")
    # Patch copy_to_clipboard to True
    monkeypatch.setattr("codesnap.cli.copy_to_clipboard", lambda x: True)
    from click.testing import CliRunner

    result = CliRunner().invoke(main, [str(project_root), "-l", "python", "-c"])
    assert result.exit_code == 0


def test_main_output_file(tmp_path):
    from click.testing import CliRunner

    pr = tmp_path / "p"
    pr.mkdir()
    (pr / "main.py").write_text("print(1)")
    output_path = tmp_path / "snap.txt"
    result = CliRunner().invoke(main, [str(pr), "-l", "python", "-o", str(output_path)])
    assert output_path.exists()
    text = output_path.read_text()
    assert "print(1)" in text


def test_main_error(monkeypatch, tmp_path):
    # Trigger an error inside main
    pr = tmp_path / "pie"
    pr.mkdir()
    (pr / "main.py").write_text("print(2)")
    from click.testing import CliRunner

    # Patch detect_language to return None to force error
    monkeypatch.setattr("codesnap.cli.detect_language", lambda path: None)
    result = CliRunner().invoke(main, [str(pr)])
    assert result.exit_code == 1
    assert "Could not auto-detect language" in result.output


def test_main_save_profile(tmp_path, monkeypatch):
    pr = tmp_path / "pr"
    pr.mkdir()
    (pr / "main.py").write_text("print(1)")
    configf = pr / "codesnap.json"
    configf.write_text("{}")
    from click.testing import CliRunner

    result = CliRunner().invoke(
        main, [str(pr), "--save-profile", "foo", "-f", str(configf), "-l", "python"]
    )
    assert "Saved profile: foo" in result.output


def test_cli_import_errors(monkeypatch):
    # Simulate ImportError for summarize
    monkeypatch.setitem(sys.modules, "codesnap.summarize", None)
    from codesnap.cli import main

    # Use '--summarize'
    result = CliRunner().invoke(main, ["--summarize", ".", "-l", "python"])
    assert "Summarization requires httpx package" in result.output


def test_cli_analyzer_import_errors(monkeypatch):
    monkeypatch.setitem(sys.modules, "codesnap.analyzer", None)
    from codesnap.cli import main

    result = CliRunner().invoke(main, ["--analyze-imports", ".", "-l", "python"])
    assert "Import analysis requires the analyzer module" in result.output
