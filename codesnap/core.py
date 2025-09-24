"""Core functionality for generating code snapshots.

This module defines the `CodeSnapshotter` class which is responsible for scanning
a source tree, filtering relevant files, formatting the directory structure,
and generating an output snapshot (text, markdown, or JSON).

Snapshots are primarily designed to be LLM-friendly, suitable for direct feeding
into models like GPT-4, Claude, or similar.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tiktoken

from codesnap.config import Config, Language
from codesnap.filters import FileFilter
from codesnap.formatters import OutputFormat, SnapshotFormatter


@dataclass
class Snapshot:
    """Represents a generated code snapshot.

    Attributes:
        content (str): Snapshot output as string (formatted for output format).
        file_count (int): Number of files included in snapshot.
        token_count (int): Approximate number of tokens in snapshot.
        truncated (bool): Whether snapshot was truncated due to token budget.
        metadata (dict[str, Any]): Additional metadata such as project name or directory tree.
    """
    content: str
    file_count: int
    token_count: int
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class CodeSnapshotter:
    """Main class for creating code snapshots.

    Scans a project directory, filters files, and renders a snapshot including
    directory structure, file contents, optional summaries, and import analysis.
    """

    def __init__(
        self,
        root_path: Path,
        language: Language,
        config: Config | None = None,
        model_encoding: str = "o200k_base",
        count_tokens: bool = True,
    ):
        """Initialize CodeSnapshotter.

        Args:
            root_path (Path): Root path to the project.
            language (Language): Programming language used.
            config (Config | None): Optional filter configuration.
            model_encoding (str): Tokenizer encoding (o200k_base or cl100k_base).
            count_tokens (bool): Whether to use tokenizer to enforce budgets.
        """
        self.root_path = root_path.resolve()
        self.language = language
        self.config = config or Config()
        self.filter = FileFilter(self.root_path, self.language, self.config)
        self.formatter = SnapshotFormatter(self.root_path, self.language)
        self.count_tokens = count_tokens
        self.tokenizer = tiktoken.get_encoding(model_encoding) if count_tokens else None

    def create_snapshot(
        self,
        max_tokens: int | None = None,
        token_buffer: int = 100,
        show_tree: bool = True,
        tree_depth: int | None = None,
        tree_style: str = "unicode",
        show_header: bool = True,
        show_footer: bool = True,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        file_summaries: dict[str, str] | None = None,
        import_analysis: dict[str, Any] | None = None,
        import_diagram: bool = False,
    ) -> Snapshot:
        """Generate a snapshot of code content.

        Args:
            max_tokens (int | None): Truncate snapshot to this token budget (None disables).
            token_buffer (int): Safety buffer to avoid exceeding token budget.
            show_tree (bool): Whether to include directory tree in output.
            tree_depth (int | None): Maximum directory tree depth.
            tree_style (str): "unicode" or "ascii".
            show_header (bool): Include snapshot header.
            show_footer (bool): Include footer.
            output_format (OutputFormat): Format of output (Markdown, Text, or JSON).
            file_summaries (dict[str, str] | None): Optional mapping of file paths to LLM summaries.
            import_analysis (dict[str, Any] | None): Optional data on project imports.
            import_diagram (bool): Whether to include a Mermaid diagram of imports.

        Returns:
            Snapshot: Generated snapshot containing content and metadata.
        """
        self.formatter.set_output_format(output_format)
        file_summaries = file_summaries or {}

        files = self._sort_files(self._collect_files())
        content_parts: list[str] = []
        total_tokens = 0
        truncated = False
        files_included = 0

        metadata: dict[str, Any] = {
            "project": self.root_path.name,
            "language": self.language.value,
            "files": [],
            "token_count": 0,
            "file_count": 0,
            "truncated": False,
        }

        effective_max_tokens = max_tokens - token_buffer if max_tokens else None

        # 1. Import Analysis Section
        total_tokens = self._handle_import_analysis(
            import_analysis,
            import_diagram,
            output_format,
            content_parts,
            total_tokens,
            effective_max_tokens,
            metadata,
        )

        # 2. Header Section
        total_tokens, early_exit = self._handle_header(
            show_header,
            output_format,
            content_parts,
            total_tokens,
            effective_max_tokens,
            metadata,
            max_tokens,
        )
        if early_exit:
            return early_exit

        # 3. File Contents Header
        if output_format == OutputFormat.MARKDOWN:
            content_parts.append("## File Contents\n")
        elif output_format == OutputFormat.TEXT:
            content_parts.append("File Contents:\n")

        # 4. Directory Tree
        total_tokens = self._handle_tree(
            show_tree,
            output_format,
            tree_depth,
            tree_style,
            content_parts,
            total_tokens,
            effective_max_tokens,
            metadata,
        )

        # 5. Files
        files_included, total_tokens, truncated = self._handle_files(
            files,
            output_format,
            file_summaries,
            content_parts,
            total_tokens,
            effective_max_tokens,
            max_tokens,
        )

        # 6. Footer
        total_tokens = self._handle_footer(
            show_footer,
            output_format,
            files_included,
            total_tokens,
            effective_max_tokens,
            content_parts,
        )

        # Finalize metadata
        metadata["token_count"] = total_tokens
        metadata["file_count"] = files_included
        metadata["truncated"] = truncated

        if output_format == OutputFormat.JSON:
            return self._create_json_snapshot(metadata)

        return Snapshot(
            content="\n".join(content_parts),
            file_count=files_included,
            token_count=total_tokens,
            truncated=truncated,
            metadata=metadata,
        )

    def _handle_import_analysis(
        self,
        import_analysis,
        import_diagram,
        output_format,
        content_parts,
        total_tokens,
        effective_max_tokens,
        metadata,
    ) -> int:
        """Optionally add import relationship analysis.

        Args:
            import_analysis (dict | None): Import analysis data.
            import_diagram (bool): Include diagram if True.
            output_format (OutputFormat): Desired output format.
            content_parts (list): Snapshot string fragments.
            total_tokens (int): Current token count.
            effective_max_tokens (int | None): Max tokens with buffer applied.
            metadata (dict): Accumulated metadata.

        Returns:
            int: Updated token count.
        """
        if not import_analysis:
            return total_tokens

        if output_format == OutputFormat.JSON:
            metadata["import_analysis"] = import_analysis
            return total_tokens

        from codesnap.analyzer import ImportAnalyzer

        content_parts.append(
            "## Import Relationships\n"
            if output_format == OutputFormat.MARKDOWN
            else "Import Relationships:\n"
        )
        try:
            analyzer = ImportAnalyzer(self.root_path)
            adjacency_list = analyzer.generate_adjacency_list()
        except ImportError:
            adjacency_list = "Import analysis not available."

        if output_format == OutputFormat.MARKDOWN:
            content_parts.append("```\n" + adjacency_list + "\n```\n")
        else:
            content_parts.append(adjacency_list + "\n")

        if import_diagram:
            try:
                mermaid = analyzer.generate_mermaid_diagram()  # type: ignore[name-defined]
            except Exception:
                mermaid = "```mermaid\ngraph TD;\n  A[Diagram not available];\n```"
            if output_format == OutputFormat.MARKDOWN:
                content_parts.append("### Import Diagram\n")
                content_parts.append(mermaid + "\n")

        return total_tokens

    def _handle_header(
        self,
        show_header,
        output_format,
        content_parts,
        total_tokens,
        effective_max_tokens,
        metadata,
        max_tokens,
    ):
        """Optionally add header section with project info."""
        if not show_header:
            return total_tokens, None

        header = self.formatter.format_header()
        if output_format != OutputFormat.JSON:
            content_parts.append(header)

        return total_tokens, None

    def _handle_tree(
        self,
        show_tree,
        output_format,
        tree_depth,
        tree_style,
        content_parts,
        total_tokens,
        effective_max_tokens,
        metadata,
    ) -> int:
        """Optionally add directory tree display."""
        if not show_tree:
            return total_tokens

        tree = self._build_tree()
        formatted_tree = self.formatter.format_tree(tree, max_depth=tree_depth, style=tree_style)

        if output_format != OutputFormat.JSON:
            content_parts.append(formatted_tree)

        metadata["directory_tree"] = tree
        return total_tokens

    def _handle_files(
        self,
        files,
        output_format,
        file_summaries,
        content_parts,
        total_tokens,
        effective_max_tokens,
        max_tokens,
    ):
        """Append file contents section."""
        files_included = 0
        truncated = False

        for file_path in files:
            relative_path = str(file_path.relative_to(self.root_path))

            if output_format == OutputFormat.JSON:
                continue

            file_section = self.formatter.format_file(
                file_path, summary=file_summaries.get(str(file_path))
            )
            content_parts.append(file_section)
            files_included += 1

        return files_included, total_tokens, truncated

    def _handle_footer(
        self,
        show_footer,
        output_format,
        files_included,
        total_tokens,
        effective_max_tokens,
        content_parts,
    ) -> int:
        """Optionally add snapshot footer with counts."""
        if show_footer and output_format != OutputFormat.JSON:
            footer = self.formatter.format_footer(files_included, total_tokens)
            content_parts.append(footer)
        return total_tokens

    def _create_json_snapshot(self, metadata: dict[str, Any]) -> Snapshot:
        """Build JSON snapshot variant."""
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
        """Collect and filter project files."""
        files: list[Path] = []
        for root, dirs, filenames in os.walk(self.root_path):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not self.filter.should_ignore(root_path / d)]
            for filename in filenames:
                file_path = root_path / filename
                if self.filter.should_ignore(file_path):
                    continue
                if (
                    self.config.include_extensions
                    and file_path.suffix not in self.config.include_extensions
                ):
                    continue
                files.append(file_path)
        if self.filter.search_terms:
            files = [f for f in files if self.filter.should_include_by_search_terms(f)]
        return files

    def _sort_files(self, files: list[Path]) -> list[Path]:
        """Order files for predictable, human-friendly output."""
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
            priority = priority_files.get(path.name, 10)
            type_priority = 0 if path.suffix in [".py", ".ts", ".js", ".tsx", ".jsx"] else 1
            return (priority, type_priority, str(path))

        return sorted(files, key=sort_key)

    def _build_tree(self) -> dict:
        """Build directory tree structure recursively."""
        tree = {"name": self.root_path.name, "type": "directory", "children": []}
        self._add_to_tree(self.root_path, tree)
        return tree

    def _add_to_tree(self, path: Path, node: dict) -> None:
        """Helper to add children into directory tree node."""
        if not path.is_dir():
            return
        try:
            children = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except (PermissionError, OSError):
            return
        if not children:
            return
        for child in children:
            is_empty_dir = child.is_dir() and not any(child.iterdir())
            if is_empty_dir or not self.filter.should_ignore(child):
                child_node = {
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "children": [] if child.is_dir() else None,
                }
                node["children"].append(child_node)
                if child.is_dir() and not is_empty_dir:
                    self._add_to_tree(child, child_node)

    def _count_tokens(self, text: str) -> int:
        """Return approximate token count for text using tokenizer."""
        if not self.count_tokens or not self.tokenizer:
            return len(text) // 4
        return len(self.tokenizer.encode(text))