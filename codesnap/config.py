"""Configuration management for codesnap."""

import json

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List


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
    exclude_patterns: list[str] = field(default_factory=list)
    max_file_lines: Optional[int] = None
    max_line_length: Optional[int] = None
    search_terms: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Optional[str | Path]) -> "Config":
        """Load configuration from a JSON file."""
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
                # No config file found
                return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract profile data if present
        profiles = data.pop("profiles", {})

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
        """Convert configuration to dictionary."""
        return {
            "ignore": self.ignore_patterns,
            "include_extensions": self.include_extensions,
            "whitelist": self.whitelist_patterns,
            "exclude": self.exclude_patterns,
            "max_file_lines": self.max_file_lines,
            "max_line_length": self.max_line_length,
            "search_terms": self.search_terms,
        }

    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        for key, value in updates.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)


class ProfileManager:
    """Manages configuration profiles."""

    def __init__(self, config_path: Optional[str | Path] = None):
        """Initialize the profile manager."""
        self.config_path = self._resolve_config_path(config_path)

    def _resolve_config_path(self, config_path: Optional[str | Path]) -> Path:
        """Resolve the configuration file path."""
        if config_path:
            return Path(config_path)

        # Try default locations
        default_paths = [
            Path.cwd() / "codesnap.json",
            Path.home() / ".config" / "codesnap" / "config.json",
        ]

        for path in default_paths:
            if path.exists():
                return path

        # If no existing config file, use the first default path
        return default_paths[0]

    def _load_config_data(self) -> Dict[str, Any]:
        """Load the configuration data from file."""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_config_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to file."""
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Load a profile from the configuration file."""
        data = self._load_config_data()
        profiles = data.get("profiles", {})
        return profiles.get(profile_name)

    def save_profile(self, profile_name: str, config: Config) -> None:
        """Save a profile to the configuration file."""
        data = self._load_config_data()

        # Ensure profiles section exists
        if "profiles" not in data:
            data["profiles"] = {}

        # Add or update profile
        data["profiles"][profile_name] = config.to_dict()

        # Save back to file
        self._save_config_data(data)

    def list_profiles(self) -> List[str]:
        """List available profiles."""
        data = self._load_config_data()
        profiles = data.get("profiles", {})
        return list(profiles.keys())

    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile from the configuration file."""
        data = self._load_config_data()
        profiles = data.get("profiles", {})

        if profile_name in profiles:
            del profiles[profile_name]
            self._save_config_data(data)
            return True

        return False


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
