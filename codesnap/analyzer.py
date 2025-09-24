"""Code analysis functionality for import and dependency tracking.

This module provides the `ImportAnalyzer` class which parses Python and JS/TS
files to detect internal and external import relationships. It can generate
dependency graphs, detect circular dependencies, find orphaned files, and
return representations in adjacency list or Mermaid diagram form.

Intended for optional snapshot enrichment in codesnap.
"""

import os
import re
from pathlib import Path
from typing import Any


class ImportAnalyzer:
    """Analyzes import relationships between files in a project."""

    def __init__(self, root_path: Path):
        """Initialize the import analyzer.

        Args:
            root_path (Path): Root project path containing the codebase.
        """
        self.root_path = root_path
        self.imports_by_file: dict[str, list[str]] = {}
        self.imported_by: dict[str, list[str]] = {}
        self.external_imports: dict[str, set[str]] = {}

    def analyze_file(self, file_path: Path) -> tuple[list[str], set[str]]:
        """Analyze imports in a single source file.

        Supports Python (`.py`, `.pyi`) and JS/TS (`.js`, `.jsx`, `.ts`, `.tsx`).

        Args:
            file_path (Path): File path to analyze.

        Returns:
            tuple[list[str], set[str]]: (internal_imports, external_imports).
                - internal_imports: List of project-relative file paths.
                - external_imports: Set of third-party/standard library imports.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            file_ext = file_path.suffix
            if file_ext in [".py", ".pyi"]:
                return self._analyze_python_imports(file_path, content)
            if file_ext in [".js", ".jsx", ".ts", ".tsx"]:
                return self._analyze_js_imports(file_path, content)
            return [], set()
        except Exception:
            return [], set()

    def _analyze_python_imports(self, file_path: Path, content: str) -> tuple[list[str], set[str]]:
        """Analyze Python imports from file content.

        Args:
            file_path (Path): File being analyzed.
            content (str): File contents.

        Returns:
            tuple[list[str], set[str]]: Internal and external imports.
        """
        internal_imports = []
        external_imports = set()
        import_patterns = [
            r"^\s*import\s+([\w.]+)(?:\s+as\s+\w+)?",
            r"^\s*from\s+([\w.]+)\s+import",
        ]
        for pattern in import_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                module_path = match.group(1)
                if self._is_internal_import(module_path, file_path):
                    import_file = self._module_to_file_path(module_path, file_path)
                    if import_file:
                        internal_imports.append(str(import_file.relative_to(self.root_path)))
                else:
                    external_imports.add(module_path)
        return internal_imports, external_imports

    def _analyze_js_imports(self, file_path: Path, content: str) -> tuple[list[str], set[str]]:
        """Analyze JavaScript/TypeScript imports from file content.

        Args:
            file_path (Path): File being analyzed.
            content (str): File contents.

        Returns:
            tuple[list[str], set[str]]: Internal and external imports.
        """
        internal_imports = []
        external_imports = set()
        import_patterns = [
            r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]",
            r"import\s+['\"]([^'\"]+)['\"]",
            r"dynamic\s*\(\s*['\"]([^'\"]+)['\"]",
        ]
        for pattern in import_patterns:
            for match in re.finditer(pattern, content):
                module_path = match.group(1)
                if not module_path.startswith(".") and not module_path.startswith("/"):
                    external_imports.add(module_path)
                else:
                    import_file = self._js_import_to_file_path(module_path, file_path)
                    if import_file:
                        internal_imports.append(str(import_file.relative_to(self.root_path)))
        return internal_imports, external_imports

    def _is_internal_import(self, module_path: str, file_path: Path) -> bool:
        """Determine if a Python import refers to an internal project file.

        Args:
            module_path (str): Import string (`import foo.bar`).
            file_path (Path): Current file path.

        Returns:
            bool: True if import is internal to project, False otherwise.
        """
        if module_path.startswith("."):
            return True
        potential_path = self.root_path / module_path.replace(".", "/")
        return (
            potential_path.exists()
            or (potential_path.parent / f"{potential_path.name}.py").exists()
            or (potential_path / "__init__.py").exists()
        )

    def _module_to_file_path(self, module_path: str, file_path: Path) -> Path | None:
        """Convert a Python module path string to a file path.

        Args:
            module_path (str): Import module string (e.g. `foo.bar`).
            file_path (Path): Source file containing the import.

        Returns:
            Path | None: Target file path if resolvable, otherwise None.
        """
        if module_path.startswith("."):
            # Handle relative imports
            parts = module_path.split(".")
            current_dir = file_path.parent
            dot_count = 0
            while parts and not parts[0]:
                dot_count += 1
                parts.pop(0)
            for _ in range(dot_count - 1):
                current_dir = current_dir.parent
            if not parts:
                return current_dir / "__init__.py"
            target = current_dir
            for part in parts:
                target = target / part
            if (target.parent / f"{target.name}.py").exists():
                return target.parent / f"{target.name}.py"
            if (target / "__init__.py").exists():
                return target / "__init__.py"
            return None

        target = self.root_path / module_path.replace(".", "/")
        if target.exists() and target.is_dir() and (target / "__init__.py").exists():
            return target / "__init__.py"
        if (target.parent / f"{target.name}.py").exists():
            return target.parent / f"{target.name}.py"
        return None

    def _js_import_to_file_path(self, import_path: str, file_path: Path) -> Path | None:
        """Convert JS/TS import path to matching file path.

        Args:
            import_path (str): Import string (relative file path).
            file_path (Path): Current file path.

        Returns:
            Path | None: Import file path if resolved, otherwise None.
        """
        if import_path.startswith("."):
            base_dir = file_path.parent
            normalized_path = os.path.normpath(os.path.join(str(base_dir), import_path))
            target = Path(normalized_path)
            extensions = [".js", ".jsx", ".ts", ".tsx", ".json"]
            if target.exists() and target.is_file():
                return target
            for ext in extensions:
                if (target.with_suffix(ext)).exists():
                    return target.with_suffix(ext)
            for ext in extensions:
                if (target / f"index{ext}").exists():
                    return target / f"index{ext}"
            return None
        return None

    def analyze_project(self, files: list[Path]) -> dict[str, Any]:
        """Analyze all imports within a project.

        Args:
            files (list[Path]): List of project files.

        Returns:
            dict[str, Any]: Import analysis including:
                - imports_by_file (dict)
                - imported_by (dict)
                - external_imports (dict)
                - core_files (list of most imported)
                - circular_dependencies (list of cycles)
                - orphaned_files (list of files not imported)
        """
        self.imports_by_file = {}
        self.imported_by = {}
        self.external_imports = {}

        for file_path in files:
            if not file_path.is_file():
                continue
            relative_path = str(file_path.relative_to(self.root_path))
            internal_imports, external_deps = self.analyze_file(file_path)
            if internal_imports or external_deps:
                self.imports_by_file[relative_path] = internal_imports
                self.external_imports[relative_path] = external_deps
                for imported_file in internal_imports:
                    if imported_file not in self.imported_by:
                        self.imported_by[imported_file] = []
                    self.imported_by[imported_file].append(relative_path)

        centrality = {file: len(importers) for file, importers in self.imported_by.items()}
        core_files = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        circular_deps = self._detect_circular_dependencies()

        return {
            "imports_by_file": self.imports_by_file,
            "imported_by": self.imported_by,
            "external_imports": self.external_imports,
            "core_files": core_files[:10],
            "circular_dependencies": circular_deps,
            "orphaned_files": self._find_orphaned_files(files),
        }

    def _detect_circular_dependencies(self) -> list[list[str]]:
        """Detect circular dependencies within internal imports.

        Returns:
            list[list[str]]: List of cycles, each as a list of file paths.
        """
        circular_deps = []
        visited = set()

        def dfs(file_path: str, path: list[str]):
            if file_path in path:
                cycle_start = path.index(file_path)
                circular_deps.append(path[cycle_start:] + [file_path])
                return
            if file_path in visited:
                return
            visited.add(file_path)
            new_path = path + [file_path]
            for imported in self.imports_by_file.get(file_path, []):
                dfs(imported, new_path)

        for file_path in self.imports_by_file:
            if file_path not in visited:
                dfs(file_path, [])
        return circular_deps

    def _find_orphaned_files(self, all_files: list[Path]) -> list[str]:
        """Find files not imported by any other file.

        Args:
            all_files (list[Path]): All project files.

        Returns:
            list[str]: Orphaned file paths.
        """
        all_file_paths = {str(f.relative_to(self.root_path)) for f in all_files if f.is_file()}
        imported_files = set()
        for imports in self.imports_by_file.values():
            imported_files.update(imports)
        orphaned = all_file_paths - imported_files

        entry_point_patterns = [
            r"^index\.(js|ts|jsx|tsx)$",
            r"^main\.(js|ts|jsx|tsx|py)$",
            r"^app\.(js|ts|jsx|tsx)$",
            r"^server\.(js|ts|jsx|tsx|py)$",
        ]
        config_patterns = [
            r"package\.json$",
            r"tsconfig\.json$",
            r"\.eslintrc",
            r"\.prettierrc",
            r"pyproject\.toml$",
            r"setup\.py$",
            r"requirements\.txt$",
            r"README\.md$",
        ]
        filtered_orphans = []
        for file in orphaned:
            is_entry = any(re.search(p, file) for p in entry_point_patterns)
            is_conf = any(re.search(p, file) for p in config_patterns)
            if not is_entry and not is_conf:
                filtered_orphans.append(file)
        return sorted(filtered_orphans)

    def generate_mermaid_diagram(self, max_files: int = 20) -> str:
        """Generate a Mermaid diagram graph of imports.

        Args:
            max_files (int): Max number of files to show.

        Returns:
            str: Mermaid code string for diagram.
        """
        if not self.imports_by_file:
            return "```mermaid\ngraph TD;\n  A[No imports found];\n```"

        central_files = sorted(self.imported_by.items(), key=lambda x: len(x[1]), reverse=True)
        important_files = set()
        for file, _ in central_files[:max_files]:
            important_files.add(file)
            important_files.update(self.imports_by_file.get(file, [])[:3])
        important_files = list(important_files)[:max_files]

        node_ids = {file: f"N{i}" for i, file in enumerate(important_files)}
        lines = ["```mermaid", "graph TD;"]

        for file, node_id in node_ids.items():
            display_name = file
            if len(display_name) > 30:
                parts = display_name.split("/")
                if len(parts) > 2:
                    display_name = f"{parts[0]}/.../{parts[-1]}"
            lines.append(f'  {node_id}["{display_name}"];')

        for file, imports in self.imports_by_file.items():
            if file in node_ids:
                for imported in imports:
                    if imported in node_ids:
                        lines.append(f"  {node_ids[file]} --> {node_ids[imported]};")

        lines.append("```")
        return "\n".join(lines)

    def generate_adjacency_list(self) -> str:
        """Generate plain-text adjacency list of import graph.

        Returns:
            str: Text representation of dependencies.
        """
        if not self.imports_by_file:
            return "No imports found."

        lines: list[str] = ["FILE DEPENDENCIES:"]
        lines.extend(self._format_file_dependencies())
        lines.append("\nIMPORTED BY:")
        lines.extend(self._format_imported_by())
        lines.append("\nCORE FILES (most imported):")
        lines.extend(self._format_core_files())

        cycles = self._detect_circular_dependencies()
        if cycles:
            lines.append("\nCIRCULAR DEPENDENCIES:")
            lines.extend(self._format_circular_deps(cycles))

        return "\n".join(lines)

    def _format_file_dependencies(self) -> list[str]:
        """Format dependency mapping for adjacency list.

        Returns:
            list[str]: List of dependency lines with internal and external imports.
        """
        result = []
        for file, imports in sorted(self.imports_by_file.items()):
            if imports or self.external_imports.get(file):
                internal = list(imports)
                external = sorted(self.external_imports.get(file, set()))
                imports_str = ", ".join(internal)
                if external:
                    if imports_str:
                        imports_str += ", "
                    imports_str += ", ".join(f"external:{ext}" for ext in external)
                result.append(f"{file} -> {imports_str}")
        return result

    def _format_imported_by(self) -> list[str]:
        """Format reverse import mapping for adjacency list."""
        result = []
        for file, importers in sorted(self.imported_by.items()):
            if importers:
                result.append(f"{file} <- {', '.join(importers)}")
        return result

    def _format_core_files(self) -> list[str]:
        """Format list of most imported core files."""
        core_list = sorted(self.imported_by.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        return [
            f"{i + 1}. {file} (imported by {len(importers)} files)"
            for i, (file, importers) in enumerate(core_list)
        ]

    def _format_circular_deps(self, cycles: list[list[str]]) -> list[str]:
        """Format circular dependencies as string list.

        Args:
            cycles (list[list[str]]): Detected cycles.

        Returns:
            list[str]: Formatted cycle lines.
        """
        return [f"{i + 1}. {' -> '.join(cycle)}" for i, cycle in enumerate(cycles)]