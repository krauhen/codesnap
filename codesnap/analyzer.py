"""Code analysis functionality for import and dependency tracking."""

import os
import re
from pathlib import Path
from typing import Any


class ImportAnalyzer:
    """Analyzes import relationships between files in a project."""

    def __init__(self, root_path: Path):
        """Initialize the import analyzer."""
        self.root_path = root_path
        self.imports_by_file: dict[str, list[str]] = {}
        self.imported_by: dict[str, list[str]] = {}
        self.external_imports: dict[str, set[str]] = {}

    def analyze_file(self, file_path: Path) -> tuple[list[str], set[str]]:
        """
        Analyze imports in a single file.
        Returns (internal_imports, external_imports)
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            file_ext = file_path.suffix

            if file_ext in [".py", ".pyi"]:
                return self._analyze_python_imports(file_path, content)
            if file_ext in [".js", ".jsx", ".ts", ".tsx"]:
                return self._analyze_js_imports(file_path, content)
            # Unsupported file type
            return [], set()
        except Exception:
            # Skip files that can't be read
            return [], set()

    def _analyze_python_imports(self, file_path: Path, content: str) -> tuple[list[str], set[str]]:
        """Analyze Python imports."""
        internal_imports = []
        external_imports = set()

        # Match import statements
        import_patterns = [
            r"^\s*import\s+([\w.]+)(?:\s+as\s+\w+)?",  # import module
            r"^\s*from\s+([\w.]+)\s+import",  # from module import ...
        ]

        for pattern in import_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                module_path = match.group(1)

                # Skip standard library and third-party imports
                if self._is_internal_import(module_path, file_path):
                    # Convert to file path
                    import_file = self._module_to_file_path(module_path, file_path)
                    if import_file:
                        internal_imports.append(str(import_file.relative_to(self.root_path)))
                else:
                    external_imports.add(module_path)

        return internal_imports, external_imports

    def _analyze_js_imports(self, file_path: Path, content: str) -> tuple[list[str], set[str]]:
        """Analyze JavaScript/TypeScript imports."""
        internal_imports = []
        external_imports = set()

        # Match import statements
        import_patterns = [
            r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",  # import ... from 'module'
            r"require\s*\(\s*['\"]([^'\"]+)['\"]",  # require('module')
            r"import\s+['\"]([^'\"]+)['\"]",  # import 'module'
            r"dynamic\s*\(\s*['\"]([^'\"]+)['\"]",  # dynamic('module')
        ]

        for pattern in import_patterns:
            for match in re.finditer(pattern, content):
                module_path = match.group(1)

                # Skip node_modules and absolute imports
                if not module_path.startswith(".") and not module_path.startswith("/"):
                    external_imports.add(module_path)
                else:
                    # Convert relative import to file path
                    import_file = self._js_import_to_file_path(module_path, file_path)
                    if import_file:
                        internal_imports.append(str(import_file.relative_to(self.root_path)))

        return internal_imports, external_imports

    def _is_internal_import(self, module_path: str, file_path: Path) -> bool:
        """Check if a Python import is internal to the project."""
        # Relative imports are always internal
        if module_path.startswith("."):
            return True

        # Check if the module exists as a file in the project
        potential_path = self.root_path / module_path.replace(".", "/")
        return (
            potential_path.exists()
            or (potential_path.parent / f"{potential_path.name}.py").exists()
            or (potential_path / "__init__.py").exists()
        )

    def _module_to_file_path(self, module_path: str, file_path: Path) -> Path | None:
        """Convert a Python module path to a file path."""
        if module_path.startswith("."):
            # Relative import
            parts = module_path.split(".")
            current_dir = file_path.parent

            # Handle dot prefixes (each dot means go up one directory)
            dot_count = 0
            while parts and not parts[0]:
                dot_count += 1
                parts.pop(0)

            # Go up directories based on dot count
            for _ in range(dot_count - 1):
                current_dir = current_dir.parent

            # Construct the path
            if not parts:
                return current_dir / "__init__.py"

            target = current_dir
            for part in parts:
                target = target / part

            # Check possible file paths
            if (target.parent / f"{target.name}.py").exists():
                return target.parent / f"{target.name}.py"
            if (target / "__init__.py").exists():
                return target / "__init__.py"
            return None
        # Absolute import
        target = self.root_path / module_path.replace(".", "/")
        if target.exists() and target.is_dir() and (target / "__init__.py").exists():
            return target / "__init__.py"
        if (target.parent / f"{target.name}.py").exists():
            return target.parent / f"{target.name}.py"
        return None

    def _js_import_to_file_path(self, import_path: str, file_path: Path) -> Path | None:
        """Convert a JS/TS import path to a file path."""
        if import_path.startswith("."):
            # Relative import
            base_dir = file_path.parent
            normalized_path = os.path.normpath(os.path.join(str(base_dir), import_path))
            target = Path(normalized_path)

            # Check possible extensions
            extensions = [".js", ".jsx", ".ts", ".tsx", ".json"]

            # Check if the path exists directly
            if target.exists() and target.is_file():
                return target

            # Check with extensions
            for ext in extensions:
                if (target.with_suffix(ext)).exists():
                    return target.with_suffix(ext)

            # Check for index files
            for ext in extensions:
                if (target / f"index{ext}").exists():
                    return target / f"index{ext}"

            return None
        # Non-relative import, probably external
        return None

    def analyze_project(self, files: list[Path]) -> dict[str, Any]:
        """
        Analyze import relationships for the entire project.
        Returns a dictionary with import information.
        """
        self.imports_by_file = {}
        self.imported_by = {}
        self.external_imports = {}

        # First pass: collect all imports
        for file_path in files:
            if not file_path.is_file():
                continue

            relative_path = str(file_path.relative_to(self.root_path))
            internal_imports, external_deps = self.analyze_file(file_path)

            if internal_imports or external_deps:
                self.imports_by_file[relative_path] = internal_imports
                self.external_imports[relative_path] = external_deps

                # Build the reverse mapping (imported_by)
                for imported_file in internal_imports:
                    if imported_file not in self.imported_by:
                        self.imported_by[imported_file] = []
                    self.imported_by[imported_file].append(relative_path)

        # Calculate centrality (how many files import each file)
        centrality = {file: len(importers) for file, importers in self.imported_by.items()}

        # Sort by centrality
        core_files = sorted(centrality.items(), key=lambda x: x[1], reverse=True)

        # Detect circular dependencies
        circular_deps = self._detect_circular_dependencies()

        # Prepare the result
        return {
            "imports_by_file": self.imports_by_file,
            "imported_by": self.imported_by,
            "external_imports": self.external_imports,
            "core_files": core_files[:10],  # Top 10 most imported
            "circular_dependencies": circular_deps,
            "orphaned_files": self._find_orphaned_files(files),
        }

    def _detect_circular_dependencies(self) -> list[list[str]]:
        """Detect circular dependencies in the imports."""
        circular_deps = []
        visited = set()

        def dfs(file_path: str, path: list[str]):
            if file_path in path:
                # Found a cycle
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
        """Find files that are not imported by any other file."""
        all_file_paths = {str(f.relative_to(self.root_path)) for f in all_files if f.is_file()}
        imported_files = set()

        for imports in self.imports_by_file.values():
            imported_files.update(imports)

        # Files that are in the project but not imported anywhere
        orphaned = all_file_paths - imported_files

        # Filter out entry points and configuration files
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
            is_entry_point = any(re.search(pattern, file) for pattern in entry_point_patterns)
            is_config = any(re.search(pattern, file) for pattern in config_patterns)

            if not is_entry_point and not is_config:
                filtered_orphans.append(file)

        return sorted(filtered_orphans)

    def generate_mermaid_diagram(self, max_files: int = 20) -> str:
        """Generate a Mermaid diagram of the import relationships."""
        if not self.imports_by_file:
            return "```mermaid\ngraph TD;\n  A[No imports found];\n```"

        # Limit to most central files to avoid overwhelming diagrams
        central_files = sorted(self.imported_by.items(), key=lambda x: len(x[1]), reverse=True)

        important_files = set()
        for file, _ in central_files[:max_files]:
            important_files.add(file)
            # Add direct imports of important files
            important_files.update(self.imports_by_file.get(file, [])[:3])

        # Limit to a reasonable number
        important_files = list(important_files)[:max_files]

        # Create node IDs (Mermaid doesn't like paths as IDs)
        node_ids = {file: f"N{i}" for i, file in enumerate(important_files)}

        lines = ["```mermaid", "graph TD;"]

        # Add nodes
        for file, node_id in node_ids.items():
            # Shorten file paths for display
            display_name = file
            if len(display_name) > 30:
                parts = display_name.split("/")
                if len(parts) > 2:
                    display_name = f"{parts[0]}/.../{parts[-1]}"

            lines.append(f'  {node_id}["{display_name}"];')

        # Add edges
        for file, imports in self.imports_by_file.items():
            if file in node_ids:
                for imported in imports:
                    if imported in node_ids:
                        lines.append(f"  {node_ids[file]} --> {node_ids[imported]};")

        lines.append("```")
        return "\n".join(lines)

    def generate_adjacency_list(self) -> str:
        """Generate a text representation of the import relationships."""
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

    # ---- new helper methods ----
    def _format_file_dependencies(self) -> list[str]:
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
        result = []
        for file, importers in sorted(self.imported_by.items()):
            if importers:
                result.append(f"{file} <- {', '.join(importers)}")
        return result

    def _format_core_files(self) -> list[str]:
        core_list = sorted(self.imported_by.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        return [
            f"{i + 1}. {file} (imported by {len(importers)} files)"
            for i, (file, importers) in enumerate(core_list)
        ]

    def _format_circular_deps(self, cycles: list[list[str]]) -> list[str]:
        return [f"{i + 1}. {' -> '.join(cycle)}" for i, cycle in enumerate(cycles)]
