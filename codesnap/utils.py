"""Utility functions for codesnap."""

import platform
import subprocess
from pathlib import Path
from typing import Optional


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard.

    Returns True if successful, False otherwise.
    """
    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0

        elif system == "Linux":
            # Try xclip first, then xsel
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    process.communicate(text.encode("utf-8"))
                    if process.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
            return False

        elif system == "Windows":
            process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0

        else:
            return False

    except Exception:
        return False


def detect_language(path: Path) -> Optional[str]:
    """
    Auto-detect the programming language of a project.

    Returns the detected language or None if unable to detect.
    """
    # Check for language-specific files
    if (path / "package.json").exists():
        # Check if TypeScript is used
        if any(path.glob("**/*.ts")) or any(path.glob("**/*.tsx")):
            return "typescript"
        return "javascript"

    elif any(
        (path / file).exists()
        for file in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
    ):
        return "python"

    # Check by file extensions
    extensions = set()
    for file_path in path.rglob("*"):
        if file_path.is_file():
            extensions.add(file_path.suffix)

    if ".py" in extensions:
        return "python"
    elif ".ts" in extensions or ".tsx" in extensions:
        return "typescript"
    elif ".js" in extensions or ".jsx" in extensions:
        return "javascript"

    return None


def format_size(num_bytes: int) -> str:
    """Format byte size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"
