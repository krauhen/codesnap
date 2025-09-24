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

        # ---------------- Python files ----------------
        (root / "main.py").write_text(
            "import utils\nfrom helpers import helper_func\nfrom .local_module import local_func\n"
        )
        (root / "utils.py").write_text(
            "import os\nimport sys\nfrom helpers import another_func\n"
        )
        (root / "helpers.py").write_text(
            "import math\ndef helper_func():\n    pass\ndef another_func():\n    pass\n"
        )
        (root / "local_module.py").write_text("def local_func():\n    pass\n")

        # Circular import
        (root / "circular1.py").write_text(
            "from circular2 import func2\ndef func1():\n    pass\n"
        )
        (root / "circular2.py").write_text(
            "from circular1 import func1\ndef func2():\n    pass\n"
        )

        # ---------------- JavaScript files ----------------
        (root / "app.js").write_text(
            "import React from 'react';\n"
            "import { Component } from 'react';\n"
            "import './styles.css';\n"
            "import utils from './utils.js';\n"
            "require('lodash');\n"
        )
        (root / "utils.js").write_text(
            "import axios from 'axios';\nimport './helpers.js';\nexport default {};\n"
        )
        (root / "helpers.js").write_text("// Helper functions\n")

        # Styles
        (root / "styles.css").write_text("body { color: red; }\n")

        yield root


def test_analyze_file_python(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    internal, external = analyzer.analyze_file(temp_project / "main.py")

    # Internal imports should be relative paths as strings
    assert "utils.py" in internal
    assert "helpers.py" in internal
    assert "local_module.py" in internal
    # main.py does not import any external modules
    assert external == set()


def test_analyze_file_javascript(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    internal, external = analyzer.analyze_file(temp_project / "app.js")

    # app.js imports utils.js and styles.css internally
    assert "utils.js" in internal
    assert "styles.css" in internal
    # External deps
    assert "react" in external
    assert "lodash" in external


def test_analyze_project(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    (temp_project / "orphaned.py").write_text("# Orphaned")

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

    # imports_by_file keys are relative strings
    assert "main.py" in result["imports_by_file"]
    assert "utils.py" in result["imports_by_file"]

    # imported_by must contain helpers.py
    assert "helpers.py" in result["imported_by"]

    # external imports for utils.py should include os
    utils_externals = result["external_imports"].get("utils.py", set())
    assert "os" in utils_externals

    # core_files should not be empty
    assert result["core_files"]

    # Circular dependencies should include circular1.py and circular2.py
    circulars = result["circular_dependencies"]
    assert any(
        {"circular1.py", "circular2.py"}.issubset(set(cycle)) for cycle in circulars
    )

    # orphaned.py should be reported
    assert any("orphaned.py" in f for f in result["orphaned_files"])


def test_detect_circular_dependencies(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    analyzer.imports_by_file = {
        "circular1.py": ["circular2.py"],
        "circular2.py": ["circular1.py"],
        "a.py": ["b.py"],
        "b.py": ["c.py"],
        "c.py": ["a.py"],
    }
    circulars = analyzer._detect_circular_dependencies()
    # Should detect both cycles
    sets = [set(c) for c in circulars]
    assert {"circular1.py", "circular2.py"}.issubset(sets[0] | sets[1])
    assert {"a.py", "b.py", "c.py"}.issubset(sets[0] | sets[1])


def test_find_orphaned_files(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    orphaned = temp_project / "orphaned.py"
    orphaned.write_text("# Orphan")

    analyzer.imports_by_file = {
        "main.py": ["utils.py", "helpers.py"],
        "utils.py": ["helpers.py"],
    }
    all_files = [
        temp_project / "main.py",
        temp_project / "utils.py",
        temp_project / "helpers.py",
        orphaned,
    ]
    orphans = analyzer._find_orphaned_files(all_files)
    assert "orphaned.py" in orphans


def test_generate_mermaid_diagram(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    analyzer.imports_by_file = {
        "main.py": ["utils.py", "helpers.py"],
        "utils.py": ["helpers.py"],
    }
    analyzer.imported_by = {
        "utils.py": ["main.py"],
        "helpers.py": ["main.py", "utils.py"],
    }

    diagram = analyzer.generate_mermaid_diagram()
    assert diagram.startswith("```mermaid")
    assert "graph TD" in diagram
    assert diagram.endswith("```")

    analyzer.imports_by_file = {}
    empty_diagram = analyzer.generate_mermaid_diagram()
    assert "No imports found" in empty_diagram


def test_module_to_file_path_handles_nonexistent(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    f = analyzer._module_to_file_path("nonexistent.module", temp_project / "main.py")
    assert f is None


def test_js_import_to_file_path_relative(temp_project):
    analyzer = ImportAnalyzer(temp_project)
    (temp_project / "components").mkdir()
    (temp_project / "components" / "Button.js").write_text("")

    target = analyzer._js_import_to_file_path("./components/Button.js", temp_project / "app.js")
    assert target.name == "Button.js"


def test_js_import_to_file_path_index(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "index.js").write_text("foo")
    f = tmp_path / "a.js"
    f.write_text("")
    analyzer = ImportAnalyzer(tmp_path)
    target = analyzer._js_import_to_file_path("./lib", f)
    assert target.name == "index.js"


def test_analyze_file_unsupported_and_read_errors(tmp_path, monkeypatch):
    analyzer = ImportAnalyzer(tmp_path)
    # Unsupported extension
    file_txt = tmp_path / "file.txt"
    file_txt.write_text("hello")
    i, e = analyzer.analyze_file(file_txt)
    assert i == []
    assert e == set()

    # Simulate read error
    f = tmp_path / "fail.py"
    f.write_text("print(1)")
    monkeypatch.setattr(Path, "read_text", lambda *_a, **_k: (_ for _ in ()).throw(OSError("bad")))
    i, e = analyzer.analyze_file(f)
    assert i == []
    assert e == set()