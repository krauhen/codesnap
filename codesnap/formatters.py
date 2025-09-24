"""Output formatting for code snapshots.

This module defines formatting options and classes for codesnap output.
It supports `Markdown`, `Plain Text`, and `JSON` output, providing tree
views, file listings, headers, and footers in LLM-friendly formats.
"""

from enum import Enum
from pathlib import Path
from codesnap.config import Language


class OutputFormat(Enum):
    """Enum representing available output formats."""

    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"


class SnapshotFormatter:
    """Formats snapshots for output.

    Provides formatting methods for headers, directory trees,
    file contents, and footers based on the selected output format.
    """

    def __init__(self, root_path: Path, language: Language):
        """Initialize the snapshot formatter.

        Args:
            root_path (Path): Project root path.
            language (Language): Project language enum.
        """
        self.root_path = root_path
        self.language = language
        self.output_format = OutputFormat.MARKDOWN

    def set_output_format(self, output_format: OutputFormat) -> None:
        """Set the output format.

        Args:
            output_format (OutputFormat): Desired output format (Markdown/Text/JSON).
        """
        self.output_format = output_format

    def format_header(self) -> str:
        """Format snapshot header.

        Returns:
            str: Header string (Markdown, Text, or empty for JSON).
        """
        if self.output_format == OutputFormat.JSON:
            return ""
        if self.output_format == OutputFormat.TEXT:
            return (
                f"Project: {self.root_path.name}\n"
                f"Language: {self.language.value}\n"
                f"Root: {self.root_path}\n"
            )
        return (
            f"# Project: {self.root_path.name}\n"
            f"Language: {self.language.value}\n"
            f"Root: {self.root_path}\n"
        )

    def format_tree(self, tree: dict, max_depth: int | None = None, style: str = "unicode") -> str:
        """Format directory tree structure.

        Args:
            tree (dict): Nested directory tree.
            max_depth (int | None): Maximum recursion depth.
            style (str): ASCII vs Unicode branch characters.

        Returns:
            str: Formatted tree output.
        """
        if self.output_format == OutputFormat.JSON:
            return ""

        lines = (
            ["Directory Structure:", ""]
            if self.output_format == OutputFormat.TEXT
            else ["## Directory Structure", "```"]
        )

        # Character schemes
        if style == "ascii":
            chars = {"branch": "|-- ", "last_branch": "`-- ", "indent": "|   ", "last_indent": "    "}
        else:
            chars = {"branch": "├── ", "last_branch": "└── ", "indent": "│   ", "last_indent": "    "}

        # Recursively format nodes
        lines.extend(
            self._format_tree_node(
                tree, prefix="", is_last=True, chars=chars, current_depth=0, max_depth=max_depth
            )
        )

        if self.output_format == OutputFormat.MARKDOWN:
            lines.append("```\n")
        else:
            lines.append("")
        return "\n".join(lines)

    def _format_tree_node(
        self,
        node: dict,
        prefix: str = "",
        is_last: bool = True,
        chars: dict[str, str] = None,
        current_depth: int = 0,
        max_depth: int | None = None,
    ) -> list[str]:
        """Recursively format a directory node.

        Args:
            node (dict): Directory node object with children.
            prefix (str): Prefix string for indentation/branching.
            is_last (bool): Whether this node is the last in its parent.
            chars (dict[str, str]): Character set for drawing.
            current_depth (int): Current recursion depth.
            max_depth (int | None): Max depth before stopping.

        Returns:
            list[str]: Formatted lines for this node and children.
        """
        lines = []
        if prefix == "":
            lines.append(f"{node['name']}/")
        else:
            connector = chars["last_branch"] if is_last else chars["branch"]
            suffix = "/" if node["type"] == "directory" else ""
            lines.append(f"{prefix}{connector}{node['name']}{suffix}")

        if max_depth is not None and current_depth >= max_depth:
            if node.get("children") and node["type"] == "directory":
                extension = chars["last_indent"] if is_last else chars["indent"]
                lines.append(f"{prefix}{extension}...")
            return lines

        if node.get("children") is not None:
            children = node["children"]
            for i, child in enumerate(children):
                extension = chars["last_indent"] if is_last else chars["indent"]
                is_last_child = i == len(children) - 1
                lines.extend(
                    self._format_tree_node(
                        child,
                        prefix + extension,
                        is_last_child,
                        chars,
                        current_depth + 1,
                        max_depth,
                    )
                )
        return lines

    def format_file(
        self,
        file_path: Path,
        max_lines: int | None = None,
        max_line_length: int | None = None,
        summary: str | None = None,
    ) -> str:
        """Format file for snapshot.

        Args:
            file_path (Path): File to include.
            max_lines (int | None): (Deprecated) Limit number of lines.
            max_line_length (int | None): (Deprecated) Limit line length.
            summary (str | None): Optional human/LLM summary.

        Returns:
            str: Formatted file representation.
        """
        relative_path = file_path.relative_to(self.root_path)
        lang_ext = self._get_language_ext(file_path)
        content = self._read_file_content(file_path, max_lines, max_line_length)

        if self.output_format == OutputFormat.JSON:
            return ""

        if content == "Binary file (not shown)":
            if self.output_format == OutputFormat.TEXT:
                return f"File: {relative_path}\n{content}\n"
            return f"### {relative_path}\n{content}\n"

        summary_text = ""
        if summary:
            if self.output_format == OutputFormat.TEXT:
                summary_text = f"Summary: {summary}\n\n"
            else:
                summary_text = f"<!-- SUMMARY: {summary} -->\n\n"

        if self.output_format == OutputFormat.TEXT:
            return f"File: {relative_path}\n{summary_text}{content}\n"

        return f"### {relative_path}\n{summary_text}```{lang_ext}\n{content}\n```\n"

    def format_footer(self, file_count: int, token_count: int) -> str:
        """Format snapshot footer.

        Args:
            file_count (int): Number of files in snapshot.
            token_count (int): Approximate token count.

        Returns:
            str: Footer string (empty for JSON).
        """
        if self.output_format == OutputFormat.JSON:
            return ""
        if self.output_format == OutputFormat.TEXT:
            return f"\nTotal files: {file_count}\nApproximate tokens: {token_count:,}"
        return f"\n---\nTotal files: {file_count}\nApproximate tokens: {token_count:,}"

    def _read_file_content(
        self,
        file_path: Path,
        max_lines: int | None = None,
        max_line_length: int | None = None,
    ) -> str:
        """Read the content of a file with optional truncation.

        Args:
            file_path (Path): File path to read.
            max_lines (int | None): (Deprecated) Maximum number of lines.
            max_line_length (int | None): (Deprecated) Max chars per line.

        Returns:
            str: File content (or message for binary/unreadable files).
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                if max_lines or max_line_length:
                    lines = []
                    for i, line in enumerate(f):
                        if max_lines and i >= max_lines:
                            lines.append(f"\n... (truncated, {sum(1 for _ in f) + 1} more lines)")
                            break
                        if max_line_length and len(line) > max_line_length:
                            lines.append(line[:max_line_length] + f"... ({len(line) - max_line_length} more chars)")
                        else:
                            lines.append(line)
                    return "".join(lines)
                return f.read()
        except UnicodeDecodeError:
            return "Binary file (not shown)"
        except Exception as e:
            return f"Error reading file: {e}"

    def _get_language_ext(self, file_path: Path) -> str:
        """Determine syntax-highlight extension string.

        Args:
            file_path (Path): File path.

        Returns:
            str: Language hint for Markdown code fences.
        """
        if not file_path.suffix:
            special_files = {
                "Dockerfile": "dockerfile",
                "dockerfile": "dockerfile",
                "Makefile": "makefile",
                "makefile": "makefile",
                ".gitignore": "gitignore",
                ".dockerignore": "dockerignore",
                ".env": "env",
                ".bashrc": "bash",
                ".zshrc": "zsh",
            }
            return special_files.get(file_path.name, "")

        if file_path.name.lower().startswith("dockerfile"):
            return "dockerfile"

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".fish": "fish",
            ".ps1": "powershell",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".xml": "xml",
            ".sql": "sql",
            ".gitignore": "gitignore",
            ".env": "env",
        }
        return ext_map.get(file_path.suffix, file_path.suffix[1:] if file_path.suffix else "")