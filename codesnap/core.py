"""Core functionality for generating code snapshots."""

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
    """Represents a generated code snapshot."""

    content: str
    file_count: int
    token_count: int
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class CodeSnapshotter:
    """Main class for creating code snapshots."""

    def __init__(
        self,
        root_path: Path,
        language: Language,
        config: Config | None = None,
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
        """Create a code snapshot."""

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

        # ----- Import Analysis Section -----
        total_tokens = self._handle_import_analysis(
            import_analysis,
            import_diagram,
            output_format,
            content_parts,
            total_tokens,
            effective_max_tokens,
            metadata,
        )

        # ----- Header Section -----
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

        # ----- Always add File Contents header -----
        if output_format == OutputFormat.MARKDOWN:
            content_parts.append("## File Contents\n")
        elif output_format == OutputFormat.TEXT:
            content_parts.append("File Contents:\n")

        # ----- Directory Tree Section -----
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

        # ----- Files Section -----
        files_included, total_tokens, truncated = self._handle_files(
            files,
            output_format,
            file_summaries,
            content_parts,
            total_tokens,
            effective_max_tokens,
            max_tokens,
        )

        # ----- Footer Section -----
        total_tokens = self._handle_footer(
            show_footer,
            output_format,
            files_included,
            total_tokens,
            effective_max_tokens,
            content_parts,
        )

        # ----- Finalize Metadata -----
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
        """Add optional import relationship data."""
        if not import_analysis:
            return total_tokens

        if output_format == OutputFormat.JSON:
            metadata["import_analysis"] = import_analysis
            return total_tokens

        # Text/Markdown output
        content_parts.append(
            "## Import Relationships\n"
            if output_format == OutputFormat.MARKDOWN
            else "Import Relationships:\n"
        )
        try:
            from codesnap.analyzer import ImportAnalyzer

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
                mermaid_diagram = analyzer.generate_mermaid_diagram()  # type: ignore[name-defined]
            except Exception:
                mermaid_diagram = "```mermaid\ngraph TD;\n  A[Import diagram not available];\n```"
            if output_format == OutputFormat.MARKDOWN:
                content_parts.append("### Import Diagram\n")
                content_parts.append(mermaid_diagram + "\n")

        if self.count_tokens and effective_max_tokens:
            import_tokens = self._count_tokens("\n".join(content_parts[-2:]))
            total_tokens += import_tokens
            if total_tokens > effective_max_tokens:
                # remove import analysis section if it breaks token budget
                del content_parts[-2:]
                total_tokens -= import_tokens
                content_parts.append("\n(Import analysis omitted due to token limit)")

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
        """Optionally add header."""
        if not show_header:
            return total_tokens, None

        header = self.formatter.format_header()
        if output_format != OutputFormat.JSON:
            content_parts.append(header)

        if self.count_tokens and effective_max_tokens:
            header_tokens = self._count_tokens(header)
            total_tokens += header_tokens
            if total_tokens > effective_max_tokens:
                if output_format == OutputFormat.JSON:
                    metadata["truncated"] = True
                    return total_tokens, self._create_json_snapshot(metadata)
                content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
                return total_tokens, Snapshot(
                    content="\n".join(content_parts),
                    file_count=0,
                    token_count=total_tokens,
                    truncated=True,
                    metadata=metadata,
                )
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
        """Optionally add directory tree."""
        if not show_tree:
            return total_tokens

        tree = self._build_tree()
        formatted_tree = self.formatter.format_tree(tree, max_depth=tree_depth, style=tree_style)

        if output_format != OutputFormat.JSON:
            token_cost = self._count_tokens(formatted_tree) if self.count_tokens else 0
            if effective_max_tokens and total_tokens + token_cost > effective_max_tokens:
                content_parts.append(
                    "Directory Structure:\n(skipped due to token limit)\n"
                    if output_format == OutputFormat.TEXT
                    else "## Directory Structure\n(skipped due to token limit)\n"
                )
            else:
                content_parts.append(formatted_tree)
                total_tokens += token_cost

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
        """Append file contents."""
        files_included = 0
        truncated = False
        max_file_lines = self.config.max_file_lines
        max_line_length = self.config.max_line_length

        for file_path in files:
            relative_path = str(file_path.relative_to(self.root_path))
            if output_format == OutputFormat.JSON:
                try:
                    text = file_path.read_text(encoding="utf-8")
                    metadata_entry = {
                        "path": relative_path,
                        "content": text,
                        "size": os.path.getsize(file_path),
                    }
                    if summary := file_summaries.get(str(file_path)):
                        metadata_entry["summary"] = summary
                    # NOTE: store in metadata
                    # caller updates metadata["files"]
                    files_included += 1
                except Exception as e:
                    # safer than bare pass → log
                    metadata_entry = {"path": relative_path, "error": str(e)}
                # JSON files go in metadata outside of here
                continue

            file_section = self.formatter.format_file(
                file_path,
                max_lines=max_file_lines,
                max_line_length=max_line_length,
                summary=file_summaries.get(str(file_path)),
            )

            token_cost = self._count_tokens(file_section) if self.count_tokens else 0
            if effective_max_tokens and total_tokens + token_cost > effective_max_tokens:
                content_parts.append(f"\n... (stopped at token limit: {max_tokens:,})")
                truncated = True
                break

            content_parts.append(file_section)
            total_tokens += token_cost
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
        """Append footer if requested."""
        if show_footer and output_format != OutputFormat.JSON:
            footer = self.formatter.format_footer(files_included, total_tokens)
            token_cost = self._count_tokens(footer) if self.count_tokens else 0
            if not effective_max_tokens or total_tokens + token_cost <= effective_max_tokens:
                content_parts.append(footer)
                total_tokens += token_cost
        return total_tokens

    def _create_json_snapshot(self, metadata: dict[str, Any]) -> Snapshot:
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
        tree = {"name": self.root_path.name, "type": "directory", "children": []}
        self._add_to_tree(self.root_path, tree)
        return tree

    def _add_to_tree(self, path: Path, node: dict) -> None:
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
        if not self.count_tokens or not self.tokenizer:
            return len(text) // 4
        return len(self.tokenizer.encode(text))
