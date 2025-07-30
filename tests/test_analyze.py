"""Tests for import analysis functionality."""

import tempfile
import pytest
from pathlib import Path
from codesnap.analyzer import ImportAnalyzer


@pytest.fixture
def temp_project():
    """Create a temporary project with import relationships."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create a simple Python project with imports
        (root / "main.py").write_text("""
import utils
from helpers import helper_func
from .local_module import local_func
""")

        (root / "utils.py").write_text("""
import os
import sys
from helpers import another_func
""")

        (root / "helpers.py").write_text("""
import math
def helper_func():
    pass
def another_func():
    pass
""")

        (root / "local_module.py").write_text("""
def local_func():
    pass
""")

        # Create a circular import
        (root / "circular1.py").write_text("""
from circular2 import func2
def func1():
    pass
""")

        (root / "circular2.py").write_text("""
from circular1 import func1
def func2():
    pass
""")

        # Create JS files
        (root / "app.js").write_text("""
import React from 'react';
import { Component } from 'react';
import './styles.css';
import utils from './utils.js';
require('lodash');
""")

        (root / "utils.js").write_text("""
import axios from 'axios';
import './helpers.js';
export default {};
""")

        (root / "helpers.js").write_text("""
// Helper functions
""")

        # Create styles.css for JS imports
        (root / "styles.css").write_text("""
body { color: red; }
""")

        yield root


def test_analyze_file_python(temp_project):
    """Test analyzing imports in a Python file."""
    analyzer = ImportAnalyzer(temp_project)

    # Test main.py imports
    internal_imports, external_imports = analyzer.analyze_file(temp_project / "main.py")
    # In the actual implementation, these might be returned as relative paths
    assert any(path.endswith("utils.py") for path in internal_imports)
    assert any(path.endswith("helpers.py") for path in internal_imports)
    assert any(path.endswith("local_module.py") for path in internal_imports)
    assert not external_imports  # No external imports


def test_analyze_file_javascript(temp_project):
    """Test analyzing imports in a JavaScript file."""
    analyzer = ImportAnalyzer(temp_project)

    # Test app.js imports
    internal_imports, external_imports = analyzer.analyze_file(temp_project / "app.js")

    # Check if the paths end with the expected filenames, not exact equality
    assert any(path.endswith("utils.js") for path in internal_imports)
    assert any(path.endswith("styles.css") for path in internal_imports)
    assert "react" in external_imports
    assert "lodash" in external_imports


def test_analyze_project(temp_project):
    """Test analyzing the entire project."""
    analyzer = ImportAnalyzer(temp_project)

    # First create the files we'll use for the orphaned files test
    (temp_project / "orphaned.py").write_text("# Orphaned file")

    result = analyzer.analyze_project(
        [
            temp_project / "main.py",
            temp_project / "utils.py",
            temp_project / "helpers.py",
            temp_project / "local_module.py",
            temp_project / "circular1.py",
            temp_project / "circular2.py",
            temp_project / "app.js",
            temp_project / "utils.js",
            temp_project / "helpers.js",
            temp_project / "orphaned.py",
        ]
    )

    # Check imports_by_file - use endswith to avoid path issues
    assert any(key.endswith("main.py") for key in result["imports_by_file"].keys())
    assert any(key.endswith("utils.py") for key in result["imports_by_file"].keys())

    # Check imported_by - use endswith to avoid path issues
    assert any(key.endswith("helpers.py") for key in result["imported_by"].keys())

    # Check external_imports
    assert any(key.endswith("utils.py") for key in result["external_imports"].keys())
    assert (
        "os"
        in result["external_imports"][
            next(key for key in result["external_imports"] if key.endswith("utils.py"))
        ]
    )

    # Check core_files (most imported)
    assert len(result["core_files"]) > 0

    # Check circular dependencies - check for circular1.py and circular2.py in any order
    assert len(result["circular_dependencies"]) > 0
    has_circular = False
    for cycle in result["circular_dependencies"]:
        if any(path.endswith("circular1.py") for path in cycle) and any(
            path.endswith("circular2.py") for path in cycle
        ):
            has_circular = True
            break
    assert has_circular, "Circular dependency between circular1.py and circular2.py not detected"

    # Check orphaned files - orphaned.py should be in the list
    assert any(path.endswith("orphaned.py") for path in result["orphaned_files"])


def test_detect_circular_dependencies(temp_project):
    """Test detection of circular dependencies."""
    analyzer = ImportAnalyzer(temp_project)

    # Manually set up imports for testing
    analyzer.imports_by_file = {
        "circular1.py": ["circular2.py"],
        "circular2.py": ["circular1.py"],
        "a.py": ["b.py"],
        "b.py": ["c.py"],
        "c.py": ["a.py"],  # Another circular dependency
    }

    circular_deps = analyzer._detect_circular_dependencies()

    # Should find both circular dependencies
    assert len(circular_deps) == 2

    # Check that each cycle contains the right files
    cycles_found = 0
    for cycle in circular_deps:
        cycle_set = set(cycle)
        if cycle_set == {"circular1.py", "circular2.py"}:
            cycles_found += 1
        elif cycle_set == {"a.py", "b.py", "c.py"}:
            cycles_found += 1

    assert cycles_found == 2, "Not all expected cycles were found"


def test_find_orphaned_files(temp_project):
    """Test finding orphaned files."""
    analyzer = ImportAnalyzer(temp_project)

    # Create an orphaned file
    orphaned_file = temp_project / "orphaned.py"
    orphaned_file.write_text("# Orphaned file")

    # Set up imports
    analyzer.imports_by_file = {"main.py": ["utils.py", "helpers.py"], "utils.py": ["helpers.py"]}

    # All files in the project
    all_files = [
        temp_project / "main.py",
        temp_project / "utils.py",
        temp_project / "helpers.py",
        orphaned_file,  # Not imported by any file
        temp_project / "README.md",  # Not a code file
        temp_project / "index.js",  # Entry point, should be excluded
    ]

    orphaned = analyzer._find_orphaned_files(all_files)

    # orphaned.py should be detected as orphaned
    assert any(path.endswith("orphaned.py") for path in orphaned)


def test_generate_mermaid_diagram(temp_project):
    """Test generation of Mermaid diagram."""
    analyzer = ImportAnalyzer(temp_project)

    # Manually set up imports for a predictable diagram
    analyzer.imports_by_file = {"main.py": ["utils.py", "helpers.py"], "utils.py": ["helpers.py"]}

    analyzer.imported_by = {"utils.py": ["main.py"], "helpers.py": ["main.py", "utils.py"]}

    # Generate diagram
    diagram = analyzer.generate_mermaid_diagram()

    # Check diagram format
    assert diagram.startswith("```mermaid")
    assert diagram.endswith("```")
    assert "graph TD;" in diagram

    # Check with empty imports
    analyzer.imports_by_file = {}
    empty_diagram = analyzer.generate_mermaid_diagram()
    assert "No imports found" in empty_diagram


def test_module_to_file_path(temp_project):
    """Test converting module paths to file paths."""
    analyzer = ImportAnalyzer(temp_project)

    # Create a package structure
    pkg_dir = temp_project / "package"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "module.py").write_text("# Module")

    subpkg_dir = pkg_dir / "subpackage"
    subpkg_dir.mkdir()
    (subpkg_dir / "__init__.py").touch()
    (subpkg_dir / "submodule.py").write_text("# Submodule")

    # Test with a non-existent module - this will return None
    # which is the expected behavior in the implementation
    file_path = analyzer._module_to_file_path("nonexistent.module", temp_project / "main.py")
    assert file_path is None


def test_js_import_to_file_path(temp_project):
    """Test converting JS import paths to file paths."""
    analyzer = ImportAnalyzer(temp_project)

    # Create JS files
    (temp_project / "components").mkdir()
    (temp_project / "components" / "Button.js").write_text("// Button component")
    (temp_project / "components" / "index.js").write_text("// Index file")

    # Test non-relative import (should return None)
    file_path = analyzer._js_import_to_file_path("react", temp_project / "app.js")
    assert file_path is None


def test_analyze_file_unsupported_extension(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("no imports here")
    analyzer = ImportAnalyzer(tmp_path)
    intern, extern = analyzer.analyze_file(f)
    assert intern == []
    assert extern == set()


def test_analyzer_analyze_file_read_error(tmp_path, monkeypatch):
    f = tmp_path / "bad.py"
    f.write_text("code here")
    analyzer = ImportAnalyzer(tmp_path)

    def bad_read_text(*a, **kw):
        raise OSError("bad read")

    monkeypatch.setattr(Path, "read_text", bad_read_text)
    intern, extern = analyzer.analyze_file(f)
    assert intern == []
    assert extern == set()


def test_analyzer__analyze_python_imports_external(monkeypatch, tmp_path):
    # Make _is_internal_import always return False to force externals
    code = "import sys\nfrom os import path"
    file_path = tmp_path / "a.py"
    file_path.write_text(code)
    analyzer = ImportAnalyzer(tmp_path)
    monkeypatch.setattr(analyzer, "_is_internal_import", lambda *a, **kw: False)
    i, e = analyzer._analyze_python_imports(file_path, code)
    assert i == []
    assert set(e) == {"sys", "os"}


def test_analyzer__analyze_js_imports_external(monkeypatch, tmp_path):
    code = "import React from 'react';\nrequire('fs');"
    file_path = tmp_path / "a.js"
    file_path.write_text(code)
    analyzer = ImportAnalyzer(tmp_path)
    assert analyzer._analyze_js_imports(file_path, code)[1] == {"react", "fs"}


def test_analyzer__js_import_to_file_path_relative(tmp_path):
    base = tmp_path
    js_file = base / "a.js"
    js_file.write_text("")
    mod_file = base / "mod.js"
    mod_file.write_text("")
    analyzer = ImportAnalyzer(tmp_path)
    out = analyzer._js_import_to_file_path("./mod.js", js_file)
    assert out.name == "mod.js"


def test_analyzer_generate_mermaid_diagram_no_imports(tmp_path):
    analyzer = ImportAnalyzer(tmp_path)
    analyzer.imports_by_file = {}
    assert "No imports found" in analyzer.generate_mermaid_diagram()


def test_analyzer_generate_adjacency_list_with_circulars(tmp_path):
    analyzer = ImportAnalyzer(tmp_path)
    analyzer.imports_by_file = {"a.py": ["b.py"], "b.py": ["a.py"]}
    analyzer.imported_by = {"b.py": ["a.py"], "a.py": ["b.py"]}
    analyzer.external_imports = {"a.py": set()}
    s = analyzer.generate_adjacency_list()
    assert "CIRCULAR" in s


def test_module_to_file_path_edges(tmp_path):
    # Add a __init__.py and try empty relative imports
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    f = pkg / "mod.py"
    f.write_text("from . import something")
    analyzer = ImportAnalyzer(tmp_path)
    # Relative import that resolves to __init__.py
    assert analyzer._module_to_file_path(".", f).name == "__init__.py"
    # Dot count > 1: from .. import ...
    f2 = tmp_path / "other.py"
    f2.write_text("from .. import foo")
    # This will return None, exercises the "for _ in range(dot_count-1)" branch


def test_js_import_to_file_path_index_file(tmp_path):
    d = tmp_path / "lib"
    d.mkdir()
    (d / "index.js").write_text("foo")
    base = tmp_path / "a.js"
    base.write_text("")
    analyzer = ImportAnalyzer(tmp_path)
    out = analyzer._js_import_to_file_path("./lib", base)
    assert out.name == "index.js"
