"""Tests for core functionality."""

import tempfile
from pathlib import Path

import pytest

from codesnap.config import Config, Language
from codesnap.core import CodeSnapshotter, Snapshot


@pytest.fixture
def temp_project():
    """Create a temporary project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create project structure
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text("def hello():\n    print('Hello, world!')\n")
        (root / "src" / "__init__.py").write_text("")
        (root / "tests").mkdir()
        (root / "tests" / "test_main.py").write_text("def test_hello():\n    pass\n")
        (root / "README.md").write_text("# Test Project\n")
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")

        # Create files that should be ignored
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "cache.pyc").write_text("compiled")

        yield root


def test_create_snapshot_basic(temp_project):
    """Test basic snapshot creation."""
    snapshotter = CodeSnapshotter(temp_project, Language.PYTHON)
    snapshot = snapshotter.create_snapshot()

    assert isinstance(snapshot, Snapshot)
    assert snapshot.file_count == 5  # main.py, __init__.py, test_main.py, README.md, pyproject.toml
    assert snapshot.token_count > 0
    assert not snapshot.truncated
    assert "# Test Project" in snapshot.content
    assert "def hello():" in snapshot.content
    assert "__pycache__" not in snapshot.content
    assert "cache.pyc" not in snapshot.content


def test_create_snapshot_with_tree(temp_project):
    """Test snapshot with directory tree."""
    snapshotter = CodeSnapshotter(temp_project, Language.PYTHON)
    snapshot = snapshotter.create_snapshot(show_tree=True)

    assert "## Directory Structure" in snapshot.content
    assert "src/" in snapshot.content
    assert "tests/" in snapshot.content
    # The tree formatting uses indentation, check for that
    assert "    ├──" in snapshot.content or "    └──" in snapshot.content


def test_create_snapshot_without_tree(temp_project):
    """Test snapshot without directory tree."""
    snapshotter = CodeSnapshotter(temp_project, Language.PYTHON)
    snapshot = snapshotter.create_snapshot(show_tree=False)

    assert "## Directory Structure" not in snapshot.content


def test_create_snapshot_with_token_limit(temp_project):
    """Test snapshot with token limit."""
    # Create a large file that will exceed token limit
    large_content = "x" * 1000  # Create content that will generate many tokens
    (temp_project / "large.py").write_text(large_content)

    snapshotter = CodeSnapshotter(temp_project, Language.PYTHON)
    snapshot = snapshotter.create_snapshot(max_tokens=100)

    assert snapshot.truncated
    assert "stopped at token limit" in snapshot.content


def test_file_sorting(temp_project):
    """Test that files are sorted by importance."""
    snapshotter = CodeSnapshotter(temp_project, Language.PYTHON)
    files = snapshotter._collect_files()
    sorted_files = snapshotter._sort_files(files)

    # pyproject.toml should come first
    assert sorted_files[0].name == "pyproject.toml"
    # README should come early
    readme_index = next(i for i, f in enumerate(sorted_files) if f.name == "README.md")
    assert readme_index < 3


def test_custom_config(temp_project):
    """Test snapshot with custom configuration."""
    config = Config(ignore_patterns=["tests/"], include_extensions=[".py", ".md"])
    snapshotter = CodeSnapshotter(temp_project, Language.PYTHON, config)
    snapshot = snapshotter.create_snapshot()

    # tests directory should be ignored
    assert "test_main.py" not in snapshot.content
    # Other files should be included
    assert "main.py" in snapshot.content
    assert "README.md" in snapshot.content
