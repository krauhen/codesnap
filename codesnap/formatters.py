"""Output formatting for code snapshots."""

from pathlib import Path
from typing import Optional

from codesnap.config import Language


class SnapshotFormatter:
    """Formats code snapshots for output."""

    def __init__(self, root_path: Path, language: Language):
        """Initialize the formatter."""
        self.root_path = root_path
        self.language = language

    def format_header(self) -> str:
        """Format the snapshot header."""
        return (
            f"# Project: {self.root_path.name}\n"
            f"Language: {self.language.value}\n"
            f"Root: {self.root_path}\n"
        )

    def format_tree(self, tree: dict) -> str:
        """Format directory tree structure."""
        lines = ["## Directory Structure", "```"]
        lines.extend(self._format_tree_node(tree))
        lines.append("```\n")
        return "\n".join(lines)

    def format_file(self, file_path: Path, max_lines: Optional[int] = None) -> str:
        """Format a single file's content."""
        relative_path = file_path.relative_to(self.root_path)

        # Determine language for syntax highlighting first
        lang_ext = self._get_language_ext(file_path)

        # Read file content - this will handle binary files
        content = self._read_file_content(file_path, max_lines)

        # Check if it's a binary file message
        if content == "Binary file (not shown)":
            # Don't include language extension for binary files
            return f"### {relative_path}\n{content}\n"

        return f"### {relative_path}\n```{lang_ext}\n{content}\n```\n"

    def format_footer(self, file_count: int, token_count: int) -> str:
        """Format the snapshot footer."""
        return f"\n---\nTotal files: {file_count}\nApproximate tokens: {token_count:,}"

    def _format_tree_node(self, node: dict, prefix: str = "", is_last: bool = True) -> list[str]:
        """Recursively format tree nodes."""
        lines = []

        if prefix == "":  # Root node
            lines.append(f"{node['name']}/")
        else:
            connector = "└── " if is_last else "├── "
            suffix = "/" if node["type"] == "directory" else ""
            lines.append(f"{prefix}{connector}{node['name']}{suffix}")

        if node.get("children"):
            children = node["children"]
            for i, child in enumerate(children):
                extension = "    " if is_last else "│   "
                is_last_child = i == len(children) - 1
                lines.extend(self._format_tree_node(child, prefix + extension, is_last_child))

        return lines

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

    def _read_file_content(self, file_path: Path, max_lines: Optional[int] = None) -> str:
        """Read file content with optional line limit."""
        try:
            # Try to read as text first
            with open(file_path, "r", encoding="utf-8") as f:
                if max_lines:
                    lines = f.readlines()
                    if len(lines) > max_lines:
                        content = "".join(lines[:max_lines])
                        content += f"\n... (truncated, {len(lines) - max_lines} more lines)"
                        return content
                    else:
                        return "".join(lines)
                else:
                    return f.read()
        except UnicodeDecodeError:
            # If it's a binary file, return a placeholder
            return "Binary file (not shown)"
        except Exception as e:
            return f"Error reading file: {e}"
