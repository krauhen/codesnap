"""File filtering logic for codesnap.

This module defines the `FileFilter` class that determines which files should be included
in a snapshot, based on ignore/exclude patterns, search terms, and language-specific defaults.
"""

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
    """Handles file filtering based on patterns, extensions, and language.

    The filter determines whether a file or directory should be included in the snapshot.
    It combines default ignore patterns, user-provided config, `.gitignore` rules,
    and optional search keyword filters.

    Attributes:
        root_path (Path): Root project directory.
        language (Language): Programming language of the project.
        config (Config): Configuration object with user rules.
        ignore_patterns (set[str]): Combined ignore patterns.
        include_extensions (set[str]): Allowed file extensions to include.
        search_terms (list[str]): Optional keyword filters for file names.
        exclude_patterns (list[str]): Explicit exclude patterns.
    """

    def __init__(self, root_path: Path, language: Language, config: Config):
        """Initialize the file filter.

        Args:
            root_path (Path): Root directory of the project.
            language (Language): Programming language.
            config (Config): Filtering configuration.
        """
        self.root_path = root_path
        self.language = language
        self.config = config
        self.ignore_patterns = self._get_ignore_patterns()
        self.include_extensions = self._get_include_extensions()
        self.search_terms = config.search_terms or []
        self.exclude_patterns = config.exclude_patterns or []

    def should_include_by_search_terms(self, path: Path) -> bool:
        """Check if a file should be included by search terms.

        Args:
            path (Path): Path to the file or directory.

        Returns:
            bool: True if the file should be included based on search term filters,
            False otherwise.
        """
        if not self.search_terms:
            return True
        path_name = path.name.lower()
        return any(term.lower() in path_name for term in self.search_terms)

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored.

        Considers default ignore patterns, `.gitignore`, exclude rules,
        search terms, whitelist, and extensions.

        Args:
            path (Path): File/directory path.

        Returns:
            bool: True if the file/directory should be skipped.
        """
        # Empty directories are not ignored
        if path.is_dir() and not any(path.iterdir()):
            return False

        # Match ignore patterns (default + .gitignore + user ignore)
        if self._matches_patterns(path, self.ignore_patterns):
            return True

        # Exclude explicit user patterns
        if self._matches_patterns(path, self.exclude_patterns):
            return True

        # Apply search filter logic
        if self.search_terms:
            if path.is_file():
                return not self.should_include_by_search_terms(path)
            return False

        # Whitelisting override
        if self.config.whitelist_patterns and not self._is_whitelisted(path):
            return True

        # Extension check
        return (
            path.is_file()
            and self.include_extensions
            and path.suffix not in self.include_extensions
        )

    def _matches_patterns(self, path: Path, patterns: list[str]) -> bool:
        """Check if path matches any of the given patterns.

        Args:
            path (Path): Path to file or directory.
            patterns (list[str]): Glob-like patterns.

        Returns:
            bool: True if matched, False otherwise.
        """
        relative_path = path.relative_to(self.root_path)
        path_str = str(relative_path)

        for pattern in patterns:
            if pattern.endswith("/"):  # Directory pattern
                if path.is_dir() and fnmatch.fnmatch(path.name + "/", pattern):
                    return True
            else:  # File match
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True
        return False

    def _is_whitelisted(self, path: Path) -> bool:
        """Check if a path is explicitly allowed by whitelist patterns.

        Args:
            path (Path): Path to check.

        Returns:
            bool: True if matched by whitelist, False if not.
        """
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
        """Compile ignore patterns from defaults, config, and `.gitignore`.

        Returns:
            set[str]: Combined expanded ignore patterns.
        """
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
        """Get the set of file extensions that should be included.

        Combines defaults for the language with user overrides.

        Returns:
            set[str]: Extensions to include.
        """
        extensions = set(DEFAULT_INCLUDE_EXTENSIONS.get(self.language, []))
        extensions.update(self.config.include_extensions)
        return extensions

    def _parse_gitignore(self, gitignore_path: Path) -> list[str]:
        """Parse `.gitignore` and extract ignore patterns.

        Args:
            gitignore_path (Path): Path to .gitignore file.

        Returns:
            list[str]: Extracted list of ignore patterns.
        """
        patterns = []
        with open(gitignore_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("!"):
                    patterns.append(line)
        return patterns
