"""Utility functions for codesnap."""

import platform
import shutil
import subprocess
from pathlib import Path


def _copy_mac(text: str) -> bool:
    """Copy text to clipboard on macOS using pbcopy."""
    pbcopy = shutil.which("pbcopy")
    if not pbcopy:
        return False
    result = subprocess.run([pbcopy], input=text.encode("utf-8"), check=False)  # noqa: S603
    return result.returncode == 0


def _copy_linux(text: str) -> bool:
    """Copy text to clipboard on Linux using xclip or xsel."""
    for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
        binary = shutil.which(cmd[0])
        if not binary:
            continue
        result = subprocess.run([binary] + cmd[1:], input=text.encode("utf-8"), check=False)  # noqa: S603
        if result.returncode == 0:
            return True
    return False


def _copy_windows(text: str) -> bool:
    """Copy text to clipboard on Windows using clip."""
    clip = shutil.which("clip")
    if not clip:
        return False
    result = subprocess.run([clip], input=text.encode("utf-8"), check=False)  # noqa: S603
    return result.returncode == 0


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard.
    Returns True if successful, False otherwise.
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _copy_mac(text)
        if system == "Linux":
            return _copy_linux(text)
        if system == "Windows":
            return _copy_windows(text)
        return False
    except Exception:
        return False


def detect_language(path: Path) -> str | None:
    """Auto-detect the programming language of a project."""
    if (path / "package.json").exists():
        if any(path.glob("**/*.ts")) or any(path.glob("**/*.tsx")):
            return "typescript"
        return "javascript"

    if any(
        (path / file).exists()
        for file in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
    ):
        return "python"

    extensions = {f.suffix for f in path.rglob("*") if f.is_file()}
    if ".py" in extensions:
        return "python"
    if ".ts" in extensions or ".tsx" in extensions:
        return "typescript"
    if ".js" in extensions or ".jsx" in extensions:
        return "javascript"

    return None


def format_size(num_bytes: int) -> str:
    """Format byte size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"
