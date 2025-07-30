"""Configuration management for codesnap."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Language(Enum):
    """Supported programming languages."""

    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    PYTHON = "python"


@dataclass
class Config:
    """Configuration for code snapshot generation."""

    ignore_patterns: list[str] = field(default_factory=list)
    include_extensions: list[str] = field(default_factory=list)
    whitelist_patterns: list[str] = field(default_factory=list)
    max_file_lines: Optional[int] = None

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        """Load configuration from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            ignore_patterns=data.get("ignore", []),
            include_extensions=data.get("include_extensions", []),
            whitelist_patterns=data.get("whitelist", []),
            max_file_lines=data.get("max_file_lines"),
        )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "ignore": self.ignore_patterns,
            "include_extensions": self.include_extensions,
            "whitelist": self.whitelist_patterns,
            "max_file_lines": self.max_file_lines,
        }


# Default patterns for different languages
DEFAULT_IGNORE_PATTERNS = {
    Language.JAVASCRIPT: [
        "node_modules/",
        "dist/",
        "build/",
        "coverage/",
        ".next/",
        "*.log",
        "*.lock",
        ".env*",
        ".cache/",
        "tmp/",
        "temp/",
        "*.min.js",
        "*.map",
        ".DS_Store",
        ".vscode/",
        ".idea/",
    ],
    Language.TYPESCRIPT: [
        "node_modules/",
        "dist/",
        "build/",
        "coverage/",
        ".next/",
        "*.log",
        "*.lock",
        ".env*",
        ".cache/",
        "tmp/",
        "temp/",
        "*.min.js",
        "*.map",
        ".DS_Store",
        ".vscode/",
        ".idea/",
        "*.tsbuildinfo",
        "out/",
    ],
    Language.PYTHON: [
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".Python",
        "venv/",
        "env/",
        "ENV/",
        ".venv/",
        "dist/",
        "build/",
        "*.egg-info/",
        ".pytest_cache/",
        ".coverage",
        "htmlcov/",
        ".tox/",
        ".mypy_cache/",
        ".ruff_cache/",
        "*.log",
        ".DS_Store",
        ".vscode/",
        ".idea/",
        "*.db",
        "*.sqlite",
        ".uv/",
        ".pdm-python",
        ".pdm-build/",
    ],
}

# Default file extensions to include
DEFAULT_INCLUDE_EXTENSIONS = {
    Language.JAVASCRIPT: [".js", ".jsx", ".json", ".md", ".yml", ".yaml"],
    Language.TYPESCRIPT: [".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml"],
    Language.PYTHON: [".py", ".pyi", ".toml", ".cfg", ".ini", ".md", ".yml", ".yaml", ".txt"],
}
