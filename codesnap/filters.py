"""File filtering logic for codesnap."""

import fnmatch
from pathlib import Path
from typing import Optional
from codesnap.config import Config, Language, DEFAULT_IGNORE_PATTERNS, DEFAULT_INCLUDE_EXTENSIONS


class FileFilter:
    """Handles file filtering based on patterns and rules."""

    def __init__(self, root_path: Path, language: Language, config: Config):
        """Initialize the file filter."""
        self.root_path = root_path
        self.language = language
        self.config = config
        self.ignore_patterns = self._get_ignore_patterns()
        self.include_extensions = self._get_include_extensions()
        self.search_terms = config.search_terms or []

    def should_include_by_search_terms(self, path: Path) -> bool:
        """
        Check if file or directory should be included based on search terms.
        Only checks file and directory names, not file contents.
        """
        if not self.search_terms:
            return True

        # Convert path name to lowercase for case-insensitive matching
        path_name = path.name.lower()

        # Check if ANY search term is in the file or directory name
        return any(term.lower() in path_name for term in self.search_terms)

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        relative_path = path.relative_to(self.root_path)
        path_str = str(relative_path)

        # Always check standard ignore patterns first
        for pattern in self.ignore_patterns:
            if pattern.endswith("/"):
                # Directory pattern
                if path.is_dir() and fnmatch.fnmatch(path.name + "/", pattern):
                    return True
            else:
                # File pattern
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True

        # If search terms are specified
        if self.search_terms:
            # For directories, only explore them if they haven't been ignored by patterns
            if path.is_dir():
                return False
            # For files, check if they match search terms
            return not self.should_include_by_search_terms(path)

        # Check whitelist (if specified)
        if self.config.whitelist_patterns:
            whitelisted = any(
                fnmatch.fnmatch(path_str, pattern) for pattern in self.config.whitelist_patterns
            )
            if not whitelisted:
                return True

        # Check file extension
        if path.is_file() and self.include_extensions:
            if path.suffix not in self.include_extensions:
                return True

        return False

    def _get_ignore_patterns(self) -> set[str]:
        """Get combined ignore patterns from defaults, gitignore, and config."""
        patterns = set(DEFAULT_IGNORE_PATTERNS.get(self.language, []))

        # Add custom ignore patterns from config
        patterns.update(self.config.ignore_patterns)

        # Read .gitignore if exists
        gitignore_path = self.root_path / ".gitignore"
        if gitignore_path.exists():
            patterns.update(self._parse_gitignore(gitignore_path))

        return patterns

    def _get_include_extensions(self) -> set[str]:
        """Get file extensions to include."""
        extensions = set(DEFAULT_INCLUDE_EXTENSIONS.get(self.language, []))
        extensions.update(self.config.include_extensions)
        return extensions

    def _parse_gitignore(self, gitignore_path: Path) -> list[str]:
        """Parse .gitignore file and return patterns."""
        patterns = []
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns
