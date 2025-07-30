"""Core functionality for generating code snapshots."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import tiktoken

from codesnap.config import Config, Language
from codesnap.filters import FileFilter
from codesnap.formatters import SnapshotFormatter


@dataclass
class Snapshot:
    """Represents a generated code snapshot."""

    content: str
    file_count: int
    token_count: int
    truncated: bool = False


class CodeSnapshotter:
    """Main class for creating code snapshots."""

    def __init__(
        self,
        root_path: Path,
        language: Language,
        config: Optional[Config] = None,
        mode_encoding: Optional[str] = "o200k_base",
    ):
        """Initialize the snapshotter."""
        self.root_path = root_path.resolve()
        self.language = language
        self.config = config or Config()
        self.filter = FileFilter(self.root_path, self.language, self.config)
        self.formatter = SnapshotFormatter(self.root_path, self.language)
        self.tokenizer = tiktoken.get_encoding(mode_encoding)

    def create_snapshot(self, max_tokens: Optional[int] = None, show_tree: bool = True) -> Snapshot:
        """Create a code snapshot."""
        # Collect files
        files = self._collect_files()

        # Sort by importance
        files = self._sort_files(files)

        # Generate content
        content_parts = []
        total_tokens = 0
        truncated = False
        files_included = 0

        # Add header
        header = self.formatter.format_header()
        content_parts.append(header)
        header_tokens = self._count_tokens(header)
        total_tokens += header_tokens

        # Check if we're already over the limit with just the header
        if max_tokens and total_tokens > max_tokens:
            content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
            return Snapshot(
                content="\n".join(content_parts),
                file_count=0,
                token_count=total_tokens,
                truncated=True,
            )

        # Add directory tree
        if show_tree:
            tree = self.formatter.format_tree(self._build_tree())
            tree_tokens = self._count_tokens(tree)

            if max_tokens and total_tokens + tree_tokens > max_tokens:
                # Skip tree if it would exceed limit
                content_parts.append("## Directory Structure\n(skipped due to token limit)\n")
            else:
                content_parts.append(tree)
                total_tokens += tree_tokens

        # Add file contents header
        content_parts.append("## File Contents\n")

        # Add files
        for file_path in files:
            file_section = self.formatter.format_file(file_path)
            section_tokens = self._count_tokens(file_section)

            if max_tokens and total_tokens + section_tokens > max_tokens:
                content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
                truncated = True
                break

            content_parts.append(file_section)
            total_tokens += section_tokens
            files_included += 1

        # Add footer
        footer = self.formatter.format_footer(files_included, total_tokens)
        footer_tokens = self._count_tokens(footer)

        # Only add footer if it doesn't exceed token limit
        if not max_tokens or total_tokens + footer_tokens <= max_tokens:
            content_parts.append(footer)
            total_tokens += footer_tokens

        return Snapshot(
            content="\n".join(content_parts),
            file_count=files_included,
            token_count=total_tokens,
            truncated=truncated,
        )

    def _collect_files(self) -> list[Path]:
        """Collect all files that should be included."""
        files = []
        for root, dirs, filenames in os.walk(self.root_path):
            root_path = Path(root)

            # Filter directories
            dirs[:] = [d for d in dirs if not self.filter.should_ignore(root_path / d)]

            # Add files
            for filename in filenames:
                file_path = root_path / filename
                if not self.filter.should_ignore(file_path):
                    files.append(file_path)

        # If search terms are used, further filter files
        if self.filter.search_terms:
            files = [f for f in files if self.filter.should_include_by_search_terms(f)]

        return files

    def _sort_files(self, files: list[Path]) -> list[Path]:
        """Sort files by importance."""
        priority_files = {
            "package.json": 0,
            "pyproject.toml": 0,
            "requirements.txt": 1,
            "setup.py": 1,
            "README.md": 2,
            "README.rst": 2,
            "README.adoc": 2,
        }

        def sort_key(path: Path) -> tuple[int, int, str]:
            # Priority by filename
            priority = priority_files.get(path.name, 10)

            # Then by file type (source files first)
            type_priority = 0 if path.suffix in [".py", ".ts", ".js", ".tsx", ".jsx"] else 1

            return (priority, type_priority, str(path))

        return sorted(files, key=sort_key)

    def _build_tree(self) -> dict:
        """Build a tree structure of the project."""
        tree = {"name": self.root_path.name, "type": "directory", "children": []}
        self._add_to_tree(self.root_path, tree)
        return tree

    def _add_to_tree(self, path: Path, node: dict) -> None:
        """Recursively add paths to tree."""
        if path.is_dir():
            children = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for child in children:
                if not self.filter.should_ignore(child):
                    child_node = {
                        "name": child.name,
                        "type": "directory" if child.is_dir() else "file",
                        "children": [] if child.is_dir() else None,
                    }
                    node["children"].append(child_node)
                    if child.is_dir():
                        self._add_to_tree(child, child_node)

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
