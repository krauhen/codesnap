"""Tests for utility functions."""

import tempfile
import pytest

from pathlib import Path
from unittest.mock import patch, MagicMock
from codesnap.utils import copy_to_clipboard, detect_language, format_size


@patch("platform.system")
@patch("subprocess.Popen")
def test_copy_to_clipboard_macos(mock_popen, mock_system):
    """Test clipboard copy on macOS."""
    mock_system.return_value = "Darwin"
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    result = copy_to_clipboard("test text")

    assert result is True
    mock_popen.assert_called_once_with(["pbcopy"], stdin=-1)
    mock_process.communicate.assert_called_once()


@patch("platform.system")
@patch("subprocess.Popen")
def test_copy_to_clipboard_linux(mock_popen, mock_system):
    """Test clipboard copy on Linux."""
    mock_system.return_value = "Linux"
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    result = copy_to_clipboard("test text")

    assert result is True
    # Should try xclip first
    mock_popen.assert_called_with(["xclip", "-selection", "clipboard"], stdin=-1)


@patch("platform.system")
@patch("subprocess.Popen")
def test_copy_to_clipboard_windows(mock_popen, mock_system):
    """Test clipboard copy on Windows."""
    mock_system.return_value = "Windows"
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    result = copy_to_clipboard("test text")

    assert result is True
    mock_popen.assert_called_once_with(["clip"], stdin=-1, shell=True)


@patch("platform.system")
def test_copy_to_clipboard_unsupported(mock_system):
    """Test clipboard copy on unsupported system."""
    mock_system.return_value = "Unknown"

    result = copy_to_clipboard("test text")

    assert result is False


def test_detect_language_javascript():
    """Test JavaScript project detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "package.json").write_text('{"name": "test"}')
        (root / "index.js").write_text("console.log('hello');")

        assert detect_language(root) == "javascript"


def test_detect_language_typescript():
    """Test TypeScript project detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "package.json").write_text('{"name": "test"}')
        (root / "src").mkdir()
        (root / "src" / "index.ts").write_text("const x: string = 'hello';")

        assert detect_language(root) == "typescript"


def test_detect_language_python():
    """Test Python project detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Test with requirements.txt
        (root / "requirements.txt").write_text("pytest>=7.0.0\n")
        assert detect_language(root) == "python"

        # Test with pyproject.toml
        (root / "requirements.txt").unlink()
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        assert detect_language(root) == "python"

        # Test with setup.py
        (root / "pyproject.toml").unlink()
        (root / "setup.py").write_text("from setuptools import setup\n")
        assert detect_language(root) == "python"


def test_detect_language_by_extension():
    """Test language detection by file extensions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Python files
        (root / "main.py").write_text("print('hello')")
        assert detect_language(root) == "python"

        # JavaScript files
        (root / "main.py").unlink()
        (root / "app.js").write_text("console.log('hello')")
        assert detect_language(root) == "javascript"

        # TypeScript files
        (root / "app.js").unlink()
        (root / "app.ts").write_text("const x: string = 'hello'")
        assert detect_language(root) == "typescript"


def test_detect_language_none():
    """Test when language cannot be detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "unknown.txt").write_text("some text")

        assert detect_language(root) is None


def test_format_size():
    """Test file size formatting."""
    test_cases = [
        (0, "0.0 B"),
        (100, "100.0 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
        (1099511627776, "1.0 TB"),
    ]

    for size, expected in test_cases:
        assert format_size(size) == expected


@patch("subprocess.Popen")
def test_copy_to_clipboard_error_handling(mock_popen):
    """Test clipboard copy error handling."""
    # Test subprocess error
    mock_popen.side_effect = Exception("Subprocess error")
    result = copy_to_clipboard("test")
    assert result is False

    # Test non-zero return code
    mock_popen.side_effect = None
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_popen.return_value = mock_process

    with patch("platform.system", return_value="Darwin"):
        result = copy_to_clipboard("test")
        assert result is False


def test_detect_language_nested_files():
    """Test language detection with nested file structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create nested Python files
        (root / "src").mkdir()
        (root / "src" / "app").mkdir()
        (root / "src" / "app" / "main.py").write_text("print('hello')")

        assert detect_language(root) == "python"

        # Create nested TypeScript files
        (root / "src" / "app" / "main.py").unlink()
        (root / "src" / "components").mkdir()
        (root / "src" / "components" / "Button.tsx").write_text("export const Button = () => {}")

        assert detect_language(root) == "typescript"


def test_detect_language_with_mixed_signals():
    """Test language detection with mixed signals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Add both JavaScript and Python files
        (root / "index.js").write_text("console.log('hello');")
        (root / "script.py").write_text("print('hello')")

        # Add package.json (JavaScript signal)
        (root / "package.json").write_text('{"name": "test"}')

        # Add requirements.txt (Python signal)
        (root / "requirements.txt").write_text("pytest>=7.0.0\n")

        # Check which language is detected (should be deterministic)
        detected = detect_language(root)

        # We're not asserting which one it should be, just that it's consistent
        assert detected in ["javascript", "python"]


def test_copy_to_clipboard_with_unicode():
    """Test clipboard copy with Unicode characters."""
    with patch("platform.system", return_value="Darwin"):
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_popen.return_value = mock_process

            # Try with Unicode text
            unicode_text = "Hello, 世界! 😊"
            result = copy_to_clipboard(unicode_text)

            assert result is True
            # Check that the text was encoded correctly
            args, kwargs = mock_process.communicate.call_args
            assert args[0] == unicode_text.encode("utf-8")


def test_copy_to_clipboard_with_very_large_text():
    """Test clipboard copy with very large text."""
    with patch("platform.system", return_value="Darwin"):
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_popen.return_value = mock_process

            # Try with a large text (1MB)
            large_text = "x" * (1024 * 1024)
            result = copy_to_clipboard(large_text)

            assert result is True
            # Check that the text was passed to communicate
            mock_process.communicate.assert_called_once()


def test_format_size_with_negative_values():
    """Test format_size with negative values."""
    # Current implementation doesn't validate for negative values
    # This test documents the current behavior
    result = format_size(-100)
    # Should return something, but we're not specifying what
    assert isinstance(result, str)


def test_detect_language_with_empty_directory():
    """Test language detection with an empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Empty directory should return None
        assert detect_language(root) is None


@patch("platform.system")
@patch("subprocess.Popen")
def test_copy_to_clipboard_linux_xsel_fallback(mock_popen, mock_system):
    """Test clipboard copy on Linux with xsel fallback."""
    mock_system.return_value = "Linux"

    # Mock xclip not found, xsel succeeds
    def side_effect_func(cmd, **kwargs):
        if cmd[0] == "xclip":
            raise FileNotFoundError("xclip not found")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc

    mock_popen.side_effect = side_effect_func

    result = copy_to_clipboard("test text")
    assert result is True

    # Should have tried xsel after xclip failed
    mock_popen.assert_called_with(["xsel", "--clipboard", "--input"], stdin=-1)
