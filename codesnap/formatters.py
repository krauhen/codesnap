"""Output formatting for code snapshots."""

from enum import Enum
from pathlib import Path

from codesnap.config import Language


class OutputFormat(Enum):
    """Output format options."""

    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"


class SnapshotFormatter:
    """Formats code snapshots for output."""

    def __init__(self, root_path: Path, language: Language):
        """Initialize the formatter."""
        self.root_path = root_path
        self.language = language
        self.output_format = OutputFormat.MARKDOWN

    def set_output_format(self, output_format: OutputFormat) -> None:
        """Set the output format."""
        self.output_format = output_format

    def format_header(self) -> str:
        """Format the snapshot header."""
        if self.output_format == OutputFormat.JSON:
            # For JSON format, we'll return an empty string and handle it in the final output
            return ""

        if self.output_format == OutputFormat.TEXT:
            return (
                f"Project: {self.root_path.name}\n"
                f"Language: {self.language.value}\n"
                f"Root: {self.root_path}\n"
            )

        # Default to Markdown
        return (
            f"# Project: {self.root_path.name}\n"
            f"Language: {self.language.value}\n"
            f"Root: {self.root_path}\n"
        )

    def format_tree(self, tree: dict, max_depth: int | None = None, style: str = "unicode") -> str:
        """Format directory tree structure."""
        if self.output_format == OutputFormat.JSON:
            # For JSON format, we'll return an empty string and handle it in the final output
            return ""

        if self.output_format == OutputFormat.TEXT:
            lines = ["Directory Structure:", ""]
        else:
            lines = ["## Directory Structure", "```"]

        # Use different characters based on style
        if style == "ascii":
            chars = {
                "branch": "|-- ",
                "last_branch": "`-- ",
                "indent": "|   ",
                "last_indent": "    ",
            }
        else:
            chars = {
                "branch": "├── ",
                "last_branch": "└── ",
                "indent": "│   ",
                "last_indent": "    ",
            }

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
        """Recursively format tree nodes."""
        lines = []
        if prefix == "":  # Root node
            lines.append(f"{node['name']}/")
        else:
            connector = chars["last_branch"] if is_last else chars["branch"]
            suffix = "/" if node["type"] == "directory" else ""
            lines.append(f"{prefix}{connector}{node['name']}{suffix}")

        # Stop recursion if we've reached max_depth
        if max_depth is not None and current_depth >= max_depth:
            if node.get("children") and node["type"] == "directory":
                extension = chars["last_indent"] if is_last else chars["indent"]
                lines.append(f"{prefix}{extension}...")
            return lines

        # Handle children, including empty directories
        if node.get("children") is not None:  # Check for None, not empty list
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
        summary: str | None = None,  # Make this parameter optional
    ) -> str:
        """Format a single file's content."""
        relative_path = file_path.relative_to(self.root_path)
        # Determine language for syntax highlighting
        lang_ext = self._get_language_ext(file_path)
        # Read file content - this will handle binary files
        content = self._read_file_content(file_path, max_lines, max_line_length)

        # Format based on output format
        if self.output_format == OutputFormat.JSON:
            # For JSON format, we'll return an empty string and handle it in the final output
            return ""

        # Check if it's a binary file message
        if content == "Binary file (not shown)":
            if self.output_format == OutputFormat.TEXT:
                return f"File: {relative_path}\n{content}\n"
            return f"### {relative_path}\n{content}\n"

        # Add summary if provided
        summary_text = ""
        if summary:
            if self.output_format == OutputFormat.TEXT:
                summary_text = f"Summary: {summary}\n\n"
            else:  # Markdown
                summary_text = f"<!-- SUMMARY: {summary} -->\n\n"

        if self.output_format == OutputFormat.TEXT:
            return f"File: {relative_path}\n{summary_text}{content}\n"

        # Default to Markdown
        return f"### {relative_path}\n{summary_text}```{lang_ext}\n{content}\n```\n"

    def format_footer(self, file_count: int, token_count: int) -> str:
        """Format the snapshot footer."""
        if self.output_format == OutputFormat.JSON:
            # For JSON format, we'll return an empty string and handle it in the final output
            return ""

        if self.output_format == OutputFormat.TEXT:
            return f"\nTotal files: {file_count}\nApproximate tokens: {token_count:,}"

        # Default to Markdown
        return f"\n---\nTotal files: {file_count}\nApproximate tokens: {token_count:,}"

    def _read_file_content(
        self,
        file_path: Path,
        max_lines: int | None = None,
        max_line_length: int | None = None,
    ) -> str:
        """Read file content with optional line limit and length limit."""
        try:
            # Try to read as text first
            with open(file_path, encoding="utf-8") as f:
                if max_lines or max_line_length:
                    lines = []
                    for i, line in enumerate(f):
                        if max_lines and i >= max_lines:
                            lines.append(f"\n... (truncated, {sum(1 for _ in f) + 1} more lines)")
                            break

                        if max_line_length and len(line) > max_line_length:
                            lines.append(
                                line[:max_line_length]
                                + f"... ({len(line) - max_line_length} more chars)"
                            )
                        else:
                            lines.append(line)

                    return "".join(lines)
                return f.read()
        except UnicodeDecodeError:
            # If it's a binary file, return a placeholder
            return "Binary file (not shown)"
        except Exception as e:
            return f"Error reading file: {e}"

    def _get_language_ext(self, file_path: Path) -> str:
        """Get language extension for syntax highlighting."""
        # Special case for files without extensions
        if not file_path.suffix:
            # Check for special filenames
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

        # Special case for Dockerfile with extension
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
