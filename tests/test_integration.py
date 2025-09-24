"""Integration tests for codesnap."""
import tempfile
import pytest
from pathlib import Path
from codesnap import CodeSnapshotter
from codesnap.config import Config, Language

@pytest.fixture
def complex_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text("def main():\n    print('Hello')\n")
        (root / "src" / "utils").mkdir()
        (root / "src" / "utils" / "helpers.py").write_text("def helper():\n    return True\n")
        (root / "tests").mkdir()
        (root / "tests" / "test_main.py").write_text("def test_main():\n    assert True\n")
        (root / "docs").mkdir()
        (root / "docs" / "README.md").write_text("# Documentation\n")
        (root / ".gitignore").write_text("*.pyc\n__pycache__/\n")
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "main.cpython-39.pyc").write_text("compiled")
        (root / "build").mkdir()
        (root / "build" / "output.bin").write_text("binary")
        yield root

def test_integration_with_search_terms(complex_project):
    config = Config(search_terms=["main"])
    snapshotter = CodeSnapshotter(complex_project, Language.PYTHON, config)
    snapshot = snapshotter.create_snapshot()
    assert "main.py" in snapshot.content
    assert "test_main.py" in snapshot.content
    assert "helpers.py" not in snapshot.content
    assert "README.md" not in snapshot.content

def test_integration_with_ignore_patterns(complex_project):
    config = Config(ignore_patterns=["*.py", "*.md", "tests/", "docs/", "src/"])
    snapshotter = CodeSnapshotter(complex_project, Language.PYTHON, config)
    snapshot = snapshotter.create_snapshot()
    assert "pyproject.toml" in snapshot.content
    assert "main.py" not in snapshot.content
    assert "test_main.py" not in snapshot.content
    assert "helpers.py" not in snapshot.content
    assert "README.md" not in snapshot.content