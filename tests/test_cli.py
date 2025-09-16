"""Tests for CLI functionality."""

import json
import sys
import tempfile
import pytest

from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from codesnap.cli import main, NullContext


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
    result = runner.invoke(main, [str(temp_python_project), "--no-tree"])
    assert result.exit_code == 0
    assert "Directory Structure" not in result.output

    result = runner.invoke(main, [str(temp_python_project), "--tree-depth", "1"])
    assert result.exit_code == 0
    assert "Directory Structure" in result.output

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


def test_NullContext_context_manager():
    nc = NullContext()
    with nc as val:
        assert val is None


def test_main_clipboard_output(tmp_path, monkeypatch):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "main.py").write_text("print('foo')")
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
    pr = tmp_path / "pie"
    pr.mkdir()
    (pr / "main.py").write_text("print(2)")
    from click.testing import CliRunner

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

    result = CliRunner().invoke(main, ["--summarize", ".", "-l", "python"])
    assert "Summarization requires httpx package" in result.output


def test_cli_analyzer_import_errors(monkeypatch):
    monkeypatch.setitem(sys.modules, "codesnap.analyzer", None)
    from codesnap.cli import main

    result = CliRunner().invoke(main, ["--analyze-imports", ".", "-l", "python"])
    assert "Import analysis requires the analyzer module" in result.output


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "main.py").write_text("def hello(): print('world')")
        (root / "test.py").write_text("def test(): pass")
        (root / "README.md").write_text("# Test Project")
        yield root


def test_cli_format_text(runner, temp_project):
    """Test text output format."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--output-format", "text"])
    assert result.exit_code == 0
    assert "Project:" in result.output  # Text format header
    assert "# Project:" not in result.output  # Not markdown


def test_cli_format_json(runner, temp_project):
    """Test JSON output format."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--output-format", "json"])
    assert result.exit_code == 0

    try:
        data = json.loads(result.output)
        assert "project" in data
        assert "language" in data
        assert "files" in data
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")


def test_cli_no_header(runner, temp_project):
    """Test without header."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--no-header"])
    assert result.exit_code == 0
    assert "# Project:" not in result.output
    assert "Language:" not in result.output


def test_cli_no_footer(runner, temp_project):
    """Test without footer."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--no-footer"])
    assert result.exit_code == 0
    assert "Total files:" not in result.output
    assert "Approximate tokens:" not in result.output


def test_cli_no_header_no_footer(runner, temp_project):
    """Test without header and footer."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--no-header", "--no-footer"])
    assert result.exit_code == 0
    assert "# Project:" not in result.output
    assert "Total files:" not in result.output


def test_cli_ignore_patterns(runner, temp_project):
    """Test ignore patterns."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--ignore", "*.py"])
    assert result.exit_code == 0
    assert "def hello():" not in result.output  # Python files should be ignored
    assert "# Test Project" in result.output  # Markdown should remain


def test_cli_multiple_ignore_patterns(runner, temp_project):
    """Test multiple ignore patterns."""
    result = runner.invoke(
        main, [str(temp_project), "-l", "python", "--ignore", "*.py", "--ignore", "*.md"]
    )
    assert result.exit_code == 0
    assert "def hello():" not in result.output
    assert "# Test Project" not in result.output


def test_cli_include_patterns(runner, temp_project):
    """Test include patterns."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--include", "*.py"])
    assert result.exit_code == 0
    assert "def hello():" in result.output


def test_cli_exclude_patterns(runner, temp_project):
    """Test exclude patterns."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--exclude", "test.py"])
    assert result.exit_code == 0
    assert "def hello():" in result.output  # main.py should be included
    assert "def test():" not in result.output  # test.py should be excluded


def test_cli_include_extensions(runner, temp_project):
    """Test include extensions."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--include-ext", ".py"])
    assert result.exit_code == 0
    assert "def hello():" in result.output


def test_cli_max_file_lines(runner, temp_project):
    """Test max file lines limit."""
    long_file = temp_project / "long.py"
    long_file.write_text("\n".join([f"line_{i} = {i}" for i in range(50)]))

    result = runner.invoke(main, [str(temp_project), "-l", "python", "--max-file-lines", "5"])
    assert result.exit_code == 0
    assert "line_0 = 0" in result.output
    assert "line_4 = 4" in result.output
    assert "line_10 = 10" not in result.output


def test_cli_max_line_length(runner, temp_project):
    """Test max line length limit."""
    long_line_file = temp_project / "long_line.py"
    long_line_file.write_text("x = '" + "a" * 200 + "'")

    result = runner.invoke(main, [str(temp_project), "-l", "python", "--max-line-length", "50"])
    assert result.exit_code == 0
    assert "more chars" in result.output  # Should show truncation


def test_cli_token_buffer(runner, temp_project):
    """Test token buffer option."""
    result = runner.invoke(
        main, [str(temp_project), "-l", "python", "--max-tokens", "100", "--token-buffer", "50"]
    )
    assert result.exit_code == 0


def test_cli_no_count_tokens(runner, temp_project):
    """Test disabling token counting."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--no-count-tokens"])
    assert result.exit_code == 0


def test_cli_model_encoding_cl100k(runner, temp_project):
    """Test cl100k_base encoding."""
    result = runner.invoke(
        main, [str(temp_project), "-l", "python", "--model-encoding", "cl100k_base"]
    )
    assert result.exit_code == 0


def test_cli_tree_depth_zero(runner, temp_project):
    """Test tree depth of 0."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--tree-depth", "0"])
    assert result.exit_code == 0
    assert "Directory Structure" in result.output


def test_cli_tree_style_ascii(runner, temp_project):
    """Test ASCII tree style."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--tree-style", "ascii"])
    assert result.exit_code == 0
    assert "|--" in result.output or "`--" in result.output


def test_cli_double_verbose(runner, temp_project):
    """Test double verbose mode."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "-vv"])
    assert result.exit_code == 0


def test_cli_triple_verbose(runner, temp_project):
    """Test triple verbose mode."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "-vvv"])
    assert result.exit_code == 0


@patch("codesnap.analyzer.ImportAnalyzer")
def test_cli_analyze_imports(mock_import_analyzer, runner, temp_project):
    mock_instance = MagicMock()
    mock_instance.analyze_project.return_value = {
        "imports_by_file": {},
        "imported_by": {},
        "external_imports": {},
        "core_files": [],
        "circular_dependencies": [],
        "orphaned_files": [],
    }
    mock_instance.generate_adjacency_list.return_value = "FILE DEPENDENCIES:\nImport Relationships"
    mock_import_analyzer.return_value = mock_instance

    result = runner.invoke(main, [str(temp_project), "-l", "python", "--analyze-imports"])
    assert result.exit_code == 0
    assert "Import Relationships" in result.output


@patch("codesnap.analyzer.ImportAnalyzer")
def test_cli_import_diagram(mock_import_analyzer, runner, temp_project):
    mock_instance = MagicMock()
    mock_instance.analyze_project.return_value = {
        "imports_by_file": {},
        "imported_by": {},
        "external_imports": {},
        "core_files": [],
        "circular_dependencies": [],
        "orphaned_files": [],
    }
    mock_instance.generate_adjacency_list.return_value = "Import Relationships"
    mock_instance.generate_mermaid_diagram.return_value = "```mermaid\ngraph TD;\n```"
    mock_import_analyzer.return_value = mock_instance

    result = runner.invoke(
        main, [str(temp_project), "-l", "python", "--analyze-imports", "--import-diagram"]
    )
    assert result.exit_code == 0
    assert "mermaid" in result.output


@patch("codesnap.summarize.CodeSummarizer")
def test_cli_summarize(mock_summarizer, runner, temp_project):
    """Test summarization flag."""
    mock_instance = MagicMock()
    mock_instance.summarize_files.return_value = {
        str(temp_project / "main.py"): "This is a summary of main.py"
    }
    mock_summarizer.return_value = mock_instance

    with patch("asyncio.run") as mock_run:
        mock_run.return_value = {str(temp_project / "main.py"): "Summary"}
        result = runner.invoke(main, [str(temp_project), "-l", "python", "--summarize"])
        assert result.exit_code == 0


def test_cli_summarize_with_options(runner, temp_project):
    """Test summarization with custom options."""
    result = runner.invoke(
        main,
        [
            str(temp_project),
            "-l",
            "python",
            "--summarize",
            "--llm-provider",
            "openai",
            "--summary-sentences",
            "5",
        ],
    )
    assert result.exit_code == 0


def test_cli_nonexistent_config_file(runner, temp_project):
    """Test with non-existent config file."""
    result = runner.invoke(
        main, [str(temp_project), "-l", "python", "--config-file", "/nonexistent/config.json"]
    )
    assert result.exit_code == 2  # Click error for non-existent file


def test_cli_invalid_config_file(runner, temp_project):
    """Test with invalid config file."""
    invalid_config = temp_project / "invalid.json"
    invalid_config.write_text("{invalid json")

    result = runner.invoke(
        main, [str(temp_project), "-l", "python", "--config-file", str(invalid_config)]
    )
    assert result.exit_code == 1  # Should handle JSON error


def test_cli_invalid_language(runner, temp_project):
    """Test with invalid language."""
    result = runner.invoke(main, [str(temp_project), "-l", "invalid"])
    assert result.exit_code == 2  # Click validation error


def test_cli_invalid_format(runner, temp_project):
    """Test with invalid format."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--output-format", "invalid"])
    assert result.exit_code == 2  # Click validation error


def test_cli_invalid_tree_style(runner, temp_project):
    """Test with invalid tree style."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--tree-style", "invalid"])
    assert result.exit_code == 2  # Click validation error


def test_cli_invalid_model_encoding(runner, temp_project):
    """Test with invalid model encoding."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--model-encoding", "invalid"])
    assert result.exit_code == 2  # Click validation error


def test_cli_complex_combination(runner, temp_project):
    """Test complex combination of options."""
    result = runner.invoke(
        main,
        [
            str(temp_project),
            "-l",
            "python",
            "--output-format",
            "markdown",
            "--max-tokens",
            "1000",
            "--tree-depth",
            "2",
            "--ignore",
            "*.pyc",
            "--include-ext",
            ".py",
            "--verbose",
            "--no-footer",
        ],
    )
    assert result.exit_code == 0


def test_cli_zero_max_tokens(runner, temp_project):
    """Test with zero max tokens."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--max-tokens", "0"])
    assert result.exit_code == 0


def test_cli_negative_values(runner, temp_project):
    """Test with negative values."""
    result = runner.invoke(main, [str(temp_project), "-l", "python", "--max-file-lines", "-1"])
    assert result.exit_code in [0, 2]


def test_cli_help(runner):
    """Test help output."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Generate LLM-friendly code snapshots" in result.output
    assert "--language" in result.output
    assert "--output-format" in result.output


def test_cli_version(runner):
    """Test version output."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0


def test_cli_empty_project(runner):
    """Test with empty project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, [tmpdir, "-l", "python"])
        assert result.exit_code == 0
