"""Configuration management for codesnap.

This module defines configuration structures and profile management used by codesnap.
Configurations determine which files are included or excluded in snapshots,
and profiles allow saving/reusing commonly used settings.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Language(Enum):
    """Enumeration of supported programming languages."""

    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    PYTHON = "python"


@dataclass
class Config:
    """Configuration for code snapshot generation.

    Attributes:
        ignore_patterns (list[str]): Glob-style patterns to ignore during scanning.
        include_extensions (list[str]): File extensions to include.
        whitelist_patterns (list[str]): File patterns to always include, regardless of ignore.
        exclude_patterns (list[str]): File patterns to always exclude.
        max_file_lines (int | None): (deprecated) Maximum number of lines per file to include.
        max_line_length (int | None): (deprecated) Maximum length per line.
        search_terms (list[str]): Only include files containing these search terms in name.
    """

    ignore_patterns: list[str] = field(default_factory=list)
    include_extensions: list[str] = field(default_factory=list)
    whitelist_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    max_file_lines: int | None = None
    max_line_length: int | None = None
    search_terms: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path | None) -> "Config":
        """Load configuration from JSON file.

        If no path is provided, attempts to load from default locations:
        - `codesnap.json` in current directory
        - `~/.config/codesnap/config.json`

        Args:
            path (str | Path | None): Path to JSON config file, or None for auto-search.

        Returns:
            Config: A configuration instance.
        """
        if not path:
            # Try default locations
            default_paths = [
                Path.cwd() / "codesnap.json",
                Path.home() / ".config" / "codesnap" / "config.json",
            ]
            for default_path in default_paths:
                if default_path.exists():
                    path = default_path
                    break
            else:
                return cls()  # No file found, return empty config

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            ignore_patterns=data.get("ignore", []),
            include_extensions=data.get("include_extensions", []),
            whitelist_patterns=data.get("whitelist", []),
            exclude_patterns=data.get("exclude", []),
            max_file_lines=data.get("max_file_lines"),
            max_line_length=data.get("max_line_length"),
            search_terms=data.get("search_terms", []),
        )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary.

        Returns:
            dict: Dictionary representation of configuration.
        """
        return {
            "ignore": self.ignore_patterns,
            "include_extensions": self.include_extensions,
            "whitelist": self.whitelist_patterns,
            "exclude": self.exclude_patterns,
            "max_file_lines": self.max_file_lines,
            "max_line_length": self.max_line_length,
            "search_terms": self.search_terms,
        }

    def update(self, updates: dict[str, Any]) -> None:
        """Update configuration fields.

        Args:
            updates (dict[str, Any]): Dictionary of config values to update.
        """
        for key, value in updates.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)


class ProfileManager:
    """Manages configuration profiles stored in JSON files.

    Profiles allow users to save commonly used snapshot settings
    and recall them later by name.

    Attributes:
        config_path (Path): Path where profiles are stored.
    """

    def __init__(self, config_path: str | Path | None = None):
        """Initialize the profile manager.

        Args:
            config_path (str | Path | None): Path to config file (optional).
                If None, uses default locations.
        """
        self.config_path = self._resolve_config_path(config_path)

    def _resolve_config_path(self, config_path: str | Path | None) -> Path:
        """Resolve the profile configuration file path.

        Args:
            config_path (str | Path | None): Provided config path or None.

        Returns:
            Path: Path to configuration file.
        """
        if config_path:
            return Path(config_path)

        # Default locations
        default_paths = [
            Path.cwd() / "codesnap.json",
            Path.home() / ".config" / "codesnap" / "config.json",
        ]
        for path in default_paths:
            if path.exists():
                return path

        # Fallback: first default path
        return default_paths[0]

    def _load_config_data(self) -> dict[str, Any]:
        """Load configuration data from file.

        Returns:
            dict[str, Any]: Loaded config data (empty dict if file missing or invalid).
        """
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_config_data(self, data: dict[str, Any]) -> None:
        """Save configuration data to file.

        Args:
            data (dict[str, Any]): Profiles to save.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_profile(self, profile_name: str) -> dict[str, Any] | None:
        """Load a saved profile.

        Args:
            profile_name (str): Profile identifier.

        Returns:
            dict[str, Any] | None: Profile configuration dictionary, or None if missing.
        """
        data = self._load_config_data()
        profiles = data.get("profiles", {})
        return profiles.get(profile_name)

    def save_profile(self, profile_name: str, config: Config) -> None:
        """Save a configuration as a profile.

        Args:
            profile_name (str): Name of the profile.
            config (Config): Configuration object to save.
        """
        data = self._load_config_data()
        if "profiles" not in data:
            data["profiles"] = {}

        data["profiles"][profile_name] = config.to_dict()
        self._save_config_data(data)

    def list_profiles(self) -> list[str]:
        """List available profiles.

        Returns:
            list[str]: Names of available profiles.
        """
        data = self._load_config_data()
        profiles = data.get("profiles", {})
        return list(profiles.keys())

    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile from storage.

        Args:
            profile_name (str): Name of profile to remove.

        Returns:
            bool: True if profile deleted, False if not found.
        """
        data = self._load_config_data()
        profiles = data.get("profiles", {})
        if profile_name in profiles:
            del profiles[profile_name]
            self._save_config_data(data)
            return True
        return False


# Default ignore patterns by language
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

# Default file extensions per language
DEFAULT_INCLUDE_EXTENSIONS = {
    Language.JAVASCRIPT: [".js", ".jsx", ".json", ".md", ".yml", ".yaml"],
    Language.TYPESCRIPT: [".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml"],
    Language.PYTHON: [".py", ".pyi", ".toml", ".cfg", ".ini", ".md", ".yml", ".yaml", ".txt"],
}
