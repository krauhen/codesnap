import fnmatch
import os
from pathlib import Path

from codesnap.config import (
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_INCLUDE_EXTENSIONS,
    Config,
    Language,
)


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
        self.exclude_patterns = config.exclude_patterns or []

    def should_include_by_search_terms(self, path: Path) -> bool:
        """
        Check if file or directory should be included based on search terms.
        Only checks file and directory names, not file contents.
        """
        if not self.search_terms:
            return True
        path_name = path.name.lower()
        return any(term.lower() in path_name for term in self.search_terms)

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        if path.is_dir() and not any(path.iterdir()):
            return False

        if self._matches_patterns(path, self.ignore_patterns):
            return True

        if self._matches_patterns(path, self.exclude_patterns):
            return True

        if self.search_terms:
            if path.is_file():
                return not self.should_include_by_search_terms(path)
            return False

        if self.config.whitelist_patterns and not self._is_whitelisted(path):
            return True

        return (
            path.is_file()
            and self.include_extensions
            and path.suffix not in self.include_extensions
        )

    def _matches_patterns(self, path: Path, patterns: list[str]) -> bool:
        """Check if path matches any given patterns (files or directories)."""
        relative_path = path.relative_to(self.root_path)
        path_str = str(relative_path)

        for pattern in patterns:
            if pattern.endswith("/"):  # Directory matching
                if path.is_dir() and fnmatch.fnmatch(path.name + "/", pattern):
                    return True
            else:  # File matching
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True
        return False

    def _is_whitelisted(self, path: Path) -> bool:
        """Check if path is included in whitelist patterns."""
        rel = path.relative_to(self.root_path)
        rel_str = str(rel)
        return any(
            rel.match(pattern)
            or rel.match("**/" + pattern)
            or fnmatch.fnmatch(rel_str, pattern)
            or fnmatch.fnmatch(rel_str.replace(os.sep, "/"), pattern)
            for pattern in self.config.whitelist_patterns
        )

    def _get_ignore_patterns(self) -> set[str]:
        """Get combined ignore patterns from defaults, gitignore, and config."""
        patterns = set(DEFAULT_IGNORE_PATTERNS.get(self.language, []))
        expanded_patterns = set()
        for pattern in patterns.union(self.config.ignore_patterns):
            expanded_patterns.add(pattern)
            expanded_patterns.add(f"*/{pattern}")
            expanded_patterns.add(f"**/{pattern}")

        gitignore_path = self.root_path / ".gitignore"
        if gitignore_path.exists():
            expanded_patterns.update(self._parse_gitignore(gitignore_path))
        return expanded_patterns

    def _get_include_extensions(self) -> set[str]:
        """Get file extensions to include."""
        extensions = set(DEFAULT_INCLUDE_EXTENSIONS.get(self.language, []))
        extensions.update(self.config.include_extensions)
        return extensions

    def _parse_gitignore(self, gitignore_path: Path) -> list[str]:
        """Parse .gitignore file and return patterns."""
        patterns = []
        with open(gitignore_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("!"):
                    patterns.append(line)
        return patterns
