import tempfile
import pytest

from pathlib import Path
from unittest.mock import patch, MagicMock
from codesnap.utils import copy_to_clipboard, detect_language, format_size


@patch("shutil.which")
@patch("subprocess.run")
@patch("platform.system")
def test_copy_to_clipboard_macos(mock_system, mock_run, mock_which):
    mock_system.return_value = "Darwin"
    mock_which.return_value = "/usr/bin/pbcopy"
    mock_run.return_value = MagicMock(returncode=0)

    result = copy_to_clipboard("test text")
    assert result is True
    mock_run.assert_called_once_with(
        ["/usr/bin/pbcopy"], input="test text".encode("utf-8"), check=False
    )


@patch("shutil.which")
@patch("subprocess.run")
@patch("platform.system")
def test_copy_to_clipboard_linux(mock_system, mock_run, mock_which):
    mock_system.return_value = "Linux"
    mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ("xclip", "xsel") else None
    mock_run.return_value = MagicMock(returncode=0)

    result = copy_to_clipboard("test text")
    assert result is True
    mock_run.assert_any_call(
        ["/usr/bin/xclip", "-selection", "clipboard"], input=b"test text", check=False
    )


@patch("shutil.which")
@patch("subprocess.run")
@patch("platform.system")
def test_copy_to_clipboard_windows(mock_system, mock_run, mock_which):
    mock_system.return_value = "Windows"
    mock_which.return_value = "C:\\Windows\\System32\\clip.exe"
    mock_run.return_value = MagicMock(returncode=0)

    result = copy_to_clipboard("test text")
    assert result is True
    mock_run.assert_called_once_with(
        ["C:\\Windows\\System32\\clip.exe"], input=b"test text", check=False
    )


@patch("shutil.which")
@patch("subprocess.run")
@patch("platform.system", return_value="Darwin")
def test_copy_to_clipboard_with_unicode(mock_system, mock_run, mock_which):
    mock_which.return_value = "/usr/bin/pbcopy"
    mock_run.return_value = MagicMock(returncode=0)

    unicode_text = "Hello, 世界! 😊"
    result = copy_to_clipboard(unicode_text)
    assert result is True
    mock_run.assert_called_once_with(
        ["/usr/bin/pbcopy"], input=unicode_text.encode("utf-8"), check=False
    )


@patch("shutil.which")
@patch("subprocess.run")
@patch("platform.system", return_value="Darwin")
def test_copy_to_clipboard_with_large_text(mock_system, mock_run, mock_which):
    mock_which.return_value = "/usr/bin/pbcopy"
    mock_run.return_value = MagicMock(returncode=0)

    big_text = "x" * (1024 * 1024)  # 1MB string
    result = copy_to_clipboard(big_text)
    assert result is True
    mock_run.assert_called_once()


@patch("shutil.which")
@patch("subprocess.run")
@patch("platform.system", return_value="Linux")
def test_copy_to_clipboard_linux_xsel_fallback(mock_system, mock_run, mock_which):
    # xclip not found, xsel found
    def which_side_effect(cmd):
        if cmd == "xclip":
            return None
        if cmd == "xsel":
            return "/usr/bin/xsel"
        return None

    mock_which.side_effect = which_side_effect
    mock_run.return_value = MagicMock(returncode=0)

    result = copy_to_clipboard("test text")
    assert result is True
    mock_run.assert_called_with(
        ["/usr/bin/xsel", "--clipboard", "--input"], input=b"test text", check=False
    )
