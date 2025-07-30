"""Tests for file filtering."""

import tempfile
from pathlib import Path

import pytest

from codesnap.config import Config, Language
from codesnap.filters import FileFilter


@pytest.fixture
def temp_project():
    """Create a temporary project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create various file types
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text("print('hello')")
        (root / "src" / "test.pyc").write_text("compiled")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "package.json").write_text("{}")
        (root / ".git").mkdir()
        (root / ".gitignore").write_text("*.log\ntmp/")
        (root / "debug.log").write_text("log data")
        (root / "README.md").write_text("# README")

        yield root


def test_default_ignore_patterns(temp_project):
    """Test default ignore patterns."""
    filter = FileFilter(temp_project, Language.PYTHON, Config())

    # Should ignore Python-specific patterns
    assert filter.should_ignore(temp_project / "src" / "test.pyc")

    # Should not ignore source files
    assert not filter.should_ignore(temp_project / "src" / "main.py")
    assert not filter.should_ignore(temp_project / "README.md")


def test_gitignore_integration(temp_project):
    """Test .gitignore file integration."""
    filter = FileFilter(temp_project, Language.PYTHON, Config())

    # Should ignore patterns from .gitignore
    assert filter.should_ignore(temp_project / "debug.log")


def test_custom_ignore_patterns(temp_project):
    """Test custom ignore patterns."""
    config = Config(ignore_patterns=["*.md", "src/"])
    filter = FileFilter(temp_project, Language.PYTHON, config)

    # Should ignore custom patterns
    assert filter.should_ignore(temp_project / "README.md")
    assert filter.should_ignore(temp_project / "src")

    # Should still apply default patterns
    assert filter.should_ignore(temp_project / "src" / "test.pyc")


def test_whitelist_patterns(temp_project):
    """Test whitelist patterns."""
    config = Config(whitelist_patterns=["src/*.py"])
    filter = FileFilter(temp_project, Language.PYTHON, config)

    # Only whitelisted files should pass
    assert not filter.should_ignore(temp_project / "src" / "main.py")

    # Non-whitelisted files should be ignored
    assert filter.should_ignore(temp_project / "README.md")
    assert filter.should_ignore(temp_project / ".gitignore")


def test_include_extensions(temp_project):
    """Test file extension filtering."""
    config = Config(include_extensions=[".txt"])
    filter = FileFilter(temp_project, Language.PYTHON, config)

    # Create a .txt file
    (temp_project / "notes.txt").write_text("notes")

    # Should include .py files (default) and .txt files (custom)
    assert not filter.should_ignore(temp_project / "src" / "main.py")
    assert not filter.should_ignore(temp_project / "notes.txt")

    # Should ignore files without included extensions
    (temp_project / "data.csv").write_text("data")
    assert filter.should_ignore(temp_project / "data.csv")


def test_directory_patterns(temp_project):
    """Test directory-specific patterns."""
    filter = FileFilter(temp_project, Language.JAVASCRIPT, Config())

    # Should ignore node_modules directory
    assert filter.should_ignore(temp_project / "node_modules")


def test_search_term_filtering(temp_project):
    """Test filtering files by search terms."""
    # Create some test files
    (temp_project / "tika_embedder.py").write_text("class TikaEmbedder: pass")
    (temp_project / "config_tika.json").write_text("{}")
    (temp_project / "other_file.txt").write_text("nothing")

    # Test single search term
    config = Config(search_terms=["tika"])
    filter = FileFilter(temp_project, Language.PYTHON, config)

    # Files with 'tika' in path should not be ignored
    assert not filter.should_ignore(temp_project / "tika_embedder.py")
    assert not filter.should_ignore(temp_project / "config_tika.json")

    # Files without 'tika' should be ignored
    assert filter.should_ignore(temp_project / "other_file.txt")


def test_multiple_search_terms(temp_project):
    """Test filtering with multiple search terms."""
    (temp_project / "tika_embedder.py").write_text("class TikaEmbedder: pass")
    (temp_project / "config_obj.json").write_text("{}")
    (temp_project / "other_file.txt").write_text("nothing")

    config = Config(search_terms=["tika", "config"])
    filter = FileFilter(temp_project, Language.PYTHON, config)

    # Files with 'tika' or 'config' in path should not be ignored
    assert not filter.should_ignore(temp_project / "tika_embedder.py")
    assert not filter.should_ignore(temp_project / "config_obj.json")

    # Files without these terms should be ignored
    assert filter.should_ignore(temp_project / "other_file.txt")
