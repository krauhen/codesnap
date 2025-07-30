"""Core functionality for generating code snapshots."""

import os
import json
import tiktoken

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
from codesnap.config import Config, Language
from codesnap.filters import FileFilter
from codesnap.formatters import SnapshotFormatter, OutputFormat


@dataclass
class Snapshot:
    """Represents a generated code snapshot."""

    content: str
    file_count: int
    token_count: int
    truncated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodeSnapshotter:
    """Main class for creating code snapshots."""

    def __init__(
        self,
        root_path: Path,
        language: Language,
        config: Optional[Config] = None,
        model_encoding: str = "o200k_base",
        count_tokens: bool = True,
    ):
        """Initialize the snapshotter."""
        self.root_path = root_path.resolve()
        self.language = language
        self.config = config or Config()
        self.filter = FileFilter(self.root_path, self.language, self.config)
        self.formatter = SnapshotFormatter(self.root_path, self.language)
        self.count_tokens = count_tokens

        if count_tokens:
            self.tokenizer = tiktoken.get_encoding(model_encoding)
        else:
            self.tokenizer = None

    def create_snapshot(
        self,
        max_tokens: Optional[int] = None,
        token_buffer: int = 100,
        show_tree: bool = True,
        tree_depth: Optional[int] = None,
        tree_style: str = "unicode",
        show_header: bool = True,
        show_footer: bool = True,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        file_summaries: Optional[Dict[str, str]] = None,
        import_analysis: Optional[Dict[str, Any]] = None,
        import_diagram: bool = False,
    ) -> Snapshot:
        """Create a code snapshot."""
        # Set output format
        self.formatter.set_output_format(output_format)

        # Use empty dict if no summaries provided
        file_summaries = file_summaries or {}

        # Collect files
        files = self._collect_files()

        # Sort by importance
        files = self._sort_files(files)

        # Generate content
        content_parts = []
        total_tokens = 0
        truncated = False
        files_included = 0
        metadata = {
            "project": self.root_path.name,
            "language": self.language.value,
            "files": [],
            "token_count": 0,
            "file_count": 0,
            "truncated": False,
        }

        # Adjust max_tokens with buffer
        effective_max_tokens = max_tokens - token_buffer if max_tokens else None

        # Add import analysis after directory tree but before file contents
        if import_analysis:
            if output_format != OutputFormat.JSON:
                if output_format == OutputFormat.MARKDOWN:
                    content_parts.append("## Import Relationships\n")
                else:
                    content_parts.append("Import Relationships:\n")

                # Add adjacency list representation
                adjacency_list = ""
                try:
                    from codesnap.analyzer import ImportAnalyzer

                    analyzer = ImportAnalyzer(self.root_path)
                    adjacency_list = analyzer.generate_adjacency_list()
                except ImportError:
                    adjacency_list = "Import analysis not available: analyzer module not found."

                if output_format == OutputFormat.MARKDOWN:
                    content_parts.append("```\n" + adjacency_list + "\n```\n")
                else:
                    content_parts.append(adjacency_list + "\n")

                # Add Mermaid diagram if requested
                if import_diagram:
                    if output_format == OutputFormat.MARKDOWN:
                        content_parts.append("### Import Diagram\n")
                        mermaid_diagram = ""
                        try:
                            mermaid_diagram = analyzer.generate_mermaid_diagram()
                        except (ImportError, NameError):
                            mermaid_diagram = (
                                "```mermaid\ngraph TD;\n  A[Import diagram not available];\n```"
                            )
                        content_parts.append(mermaid_diagram + "\n")
                    else:
                        content_parts.append("Import diagram not available in text format.\n")

                # Update token count if needed
                if self.count_tokens and effective_max_tokens:
                    import_section = "\n".join(content_parts[-2:])  # Get the added sections
                    import_tokens = self._count_tokens(import_section)
                    total_tokens += import_tokens

                    # Check if we've exceeded the token limit
                    if total_tokens > effective_max_tokens:
                        # Remove the import analysis section
                        content_parts = content_parts[:-2]
                        total_tokens -= import_tokens
                        content_parts.append("\n(Import analysis omitted due to token limit)")
            else:
                # For JSON output, add to metadata
                metadata["import_analysis"] = import_analysis

        # Add file contents header
        if output_format == OutputFormat.MARKDOWN:
            content_parts.append("## File Contents\n")
        elif output_format == OutputFormat.TEXT:
            content_parts.append("File Contents:\n")

        # Add header
        if show_header:
            header = self.formatter.format_header()
            if output_format != OutputFormat.JSON:
                content_parts.append(header)

            if self.count_tokens and effective_max_tokens:
                header_tokens = self._count_tokens(header)
                total_tokens += header_tokens

                # Check if we're already over the limit with just the header
                if total_tokens > effective_max_tokens:
                    if output_format == OutputFormat.JSON:
                        metadata["truncated"] = True
                        return self._create_json_snapshot(metadata)
                    else:
                        content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
                        return Snapshot(
                            content="\n".join(content_parts),
                            file_count=0,
                            token_count=total_tokens,
                            truncated=True,
                            metadata=metadata,
                        )

        # Add directory tree
        if show_tree:
            tree = self._build_tree()
            formatted_tree = self.formatter.format_tree(
                tree, max_depth=tree_depth, style=tree_style
            )

            if output_format != OutputFormat.JSON:
                if self.count_tokens and effective_max_tokens:
                    tree_tokens = self._count_tokens(formatted_tree)
                    if total_tokens + tree_tokens > effective_max_tokens:
                        # Skip tree if it would exceed limit
                        if output_format == OutputFormat.TEXT:
                            content_parts.append(
                                "Directory Structure:\n(skipped due to token limit)\n"
                            )
                        else:
                            content_parts.append(
                                "## Directory Structure\n(skipped due to token limit)\n"
                            )
                    else:
                        content_parts.append(formatted_tree)
                        total_tokens += tree_tokens
                else:
                    content_parts.append(formatted_tree)

            # Add tree to metadata
            metadata["directory_tree"] = tree

        # Add file contents header
        if output_format == OutputFormat.MARKDOWN:
            content_parts.append("## File Contents\n")
        elif output_format == OutputFormat.TEXT:
            content_parts.append("File Contents:\n")

        # Add files
        max_file_lines = self.config.max_file_lines
        max_line_length = self.config.max_line_length

        for file_path in files:
            relative_path = str(file_path.relative_to(self.root_path))

            if output_format == OutputFormat.JSON:
                # For JSON, collect file content separately
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    file_info = {
                        "path": relative_path,
                        "content": file_content,
                        "size": os.path.getsize(file_path),
                    }
                    # Add summary if available
                    summary = file_summaries.get(str(file_path))
                    if summary:
                        file_info["summary"] = summary
                    metadata["files"].append(file_info)
                    files_included += 1
                except (UnicodeDecodeError, Exception):
                    # Skip binary or unreadable files for JSON output
                    pass
            else:
                file_section = self.formatter.format_file(
                    file_path,
                    max_lines=max_file_lines,
                    max_line_length=max_line_length,
                    summary=file_summaries.get(str(file_path)) if file_summaries else None,
                )

                if self.count_tokens and effective_max_tokens:
                    section_tokens = self._count_tokens(file_section)
                    if total_tokens + section_tokens > effective_max_tokens:
                        if output_format == OutputFormat.TEXT:
                            content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
                        else:
                            content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
                        truncated = True
                        break

                content_parts.append(file_section)

                if self.count_tokens:
                    total_tokens += self._count_tokens(file_section)

                files_included += 1

        # Add footer
        if show_footer:
            if output_format != OutputFormat.JSON:
                footer = self.formatter.format_footer(files_included, total_tokens)

                if (
                    not self.count_tokens
                    or not effective_max_tokens
                    or total_tokens + self._count_tokens(footer) <= effective_max_tokens
                ):
                    content_parts.append(footer)
                    if self.count_tokens:
                        total_tokens += self._count_tokens(footer)

        # Update metadata
        metadata["token_count"] = total_tokens
        metadata["file_count"] = files_included
        metadata["truncated"] = truncated

        # Create JSON output if requested
        if output_format == OutputFormat.JSON:
            return self._create_json_snapshot(metadata)

        # Create regular snapshot
        return Snapshot(
            content="\n".join(content_parts),
            file_count=files_included,
            token_count=total_tokens,
            truncated=truncated,
            metadata=metadata,
        )

    def _create_json_snapshot(self, metadata: Dict[str, Any]) -> Snapshot:
        """Create a JSON format snapshot."""
        json_content = json.dumps(metadata, indent=2)
        token_count = self._count_tokens(json_content) if self.count_tokens else 0

        return Snapshot(
            content=json_content,
            file_count=metadata["file_count"],
            token_count=token_count,
            truncated=metadata["truncated"],
            metadata=metadata,
        )

    def _collect_files(self) -> list[Path]:
        """Collect all files that should be included."""
        files = []
        for root, dirs, filenames in os.walk(self.root_path):
            root_path = Path(root)

            # Filter directories first
            dirs[:] = [d for d in dirs if not self.filter.should_ignore(root_path / d)]

            # Add files, strictly filtering
            for filename in filenames:
                file_path = root_path / filename

                # Strict filtering: ignore if pattern matches
                if self.filter.should_ignore(file_path):
                    continue

                # Additional extension check if configured
                if (
                    self.config.include_extensions
                    and file_path.suffix not in self.config.include_extensions
                ):
                    continue

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
            # Get all children
            try:
                children = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except (PermissionError, OSError):
                # Skip directories we can't read
                return

            # Check if this is an empty directory
            if not children:
                # It's an empty directory, but we still want to include it
                return  # Node already has an empty children list

            for child in children:
                # Special handling for empty directories - always include them
                is_empty_dir = child.is_dir() and not any(child.iterdir())

                # Skip files/dirs that should be ignored, but always include empty dirs
                if is_empty_dir or not self.filter.should_ignore(child):
                    child_node = {
                        "name": child.name,
                        "type": "directory" if child.is_dir() else "file",
                        "children": [] if child.is_dir() else None,
                    }
                    node["children"].append(child_node)

                    # Only recurse if it's a non-empty directory
                    if child.is_dir() and not is_empty_dir:
                        self._add_to_tree(child, child_node)

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not self.count_tokens or not self.tokenizer:
            # Return an estimate if not counting tokens
            return len(text) // 4

        return len(self.tokenizer.encode(text))
