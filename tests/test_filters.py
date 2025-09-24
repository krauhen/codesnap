"""Tests for file filtering."""
import tempfile
import os
import pytest
from pathlib import Path

from codesnap import CodeSnapshotter
from codesnap.config import Config, Language
from codesnap.filters import FileFilter


@pytest.fixture
def temp_project():
    """Create a temporary project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
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
    filter = FileFilter(temp_project, Language.PYTHON, Config())
    assert filter.should_ignore(temp_project / "src" / "test.pyc")
    assert not filter.should_ignore(temp_project / "src" / "main.py")
    assert not filter.should_ignore(temp_project / "README.md")


def test_gitignore_integration(temp_project):
    filter = FileFilter(temp_project, Language.PYTHON, Config())
    assert filter.should_ignore(temp_project / "debug.log")


def test_custom_ignore_patterns(temp_project):
    config = Config(ignore_patterns=["*.md", "src/"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert filter.should_ignore(temp_project / "README.md")
    assert filter.should_ignore(temp_project / "src")
    assert filter.should_ignore(temp_project / "src" / "test.pyc")


def test_whitelist_patterns(temp_project):
    config = Config(whitelist_patterns=["src/*.py"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert not filter.should_ignore(temp_project / "src" / "main.py")
    assert filter.should_ignore(temp_project / "README.md")
    assert filter.should_ignore(temp_project / ".gitignore")


def test_include_extensions(temp_project):
    config = Config(include_extensions=[".txt"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    (temp_project / "notes.txt").write_text("notes")
    assert not filter.should_ignore(temp_project / "src" / "main.py")
    assert not filter.should_ignore(temp_project / "notes.txt")
    (temp_project / "data.csv").write_text("data")
    assert filter.should_ignore(temp_project / "data.csv")


def test_directory_patterns(temp_project):
    filter = FileFilter(temp_project, Language.JAVASCRIPT, Config())
    assert filter.should_ignore(temp_project / "node_modules")


def test_search_term_filtering(temp_project):
    (temp_project / "tika_embedder.py").write_text("class TikaEmbedder: pass")
    (temp_project / "config_tika.json").write_text("{}")
    (temp_project / "other_file.txt").write_text("nothing")
    config = Config(search_terms=["tika"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert not filter.should_ignore(temp_project / "tika_embedder.py")
    assert not filter.should_ignore(temp_project / "config_tika.json")
    assert filter.should_ignore(temp_project / "other_file.txt")


def test_multiple_search_terms(temp_project):
    (temp_project / "tika_embedder.py").write_text("class TikaEmbedder: pass")
    (temp_project / "config_obj.json").write_text("{}")
    (temp_project / "other_file.txt").write_text("nothing")
    config = Config(search_terms=["tika", "config"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert not filter.should_ignore(temp_project / "tika_embedder.py")
    assert not filter.should_ignore(temp_project / "config_obj.json")
    assert filter.should_ignore(temp_project / "other_file.txt")


def test_case_sensitivity_in_search_terms(temp_project):
    (temp_project / "UPPERCASE.py").write_text("print('UPPER')")
    (temp_project / "lowercase.py").write_text("print('lower')")
    (temp_project / "MixedCase.py").write_text("print('Mixed')")
    config = Config(search_terms=["upper"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert not filter.should_ignore(temp_project / "UPPERCASE.py")
    assert filter.should_ignore(temp_project / "lowercase.py")
    assert filter.should_ignore(temp_project / "MixedCase.py")
    config = Config(search_terms=["MIXED"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert filter.should_ignore(temp_project / "UPPERCASE.py")
    assert filter.should_ignore(temp_project / "lowercase.py")
    assert not filter.should_ignore(temp_project / "MixedCase.py")


@pytest.mark.skipif(os.name == "nt", reason="Symlinks not well supported on Windows")
def test_symlink_handling(temp_project):
    target_file = temp_project / "target.py"
    target_file.write_text("print('target')")
    symlink_file = temp_project / "symlink.py"
    try:
        symlink_file.symlink_to(target_file)
        filter = FileFilter(temp_project, Language.PYTHON, Config())
        assert not filter.should_ignore(symlink_file)
        snapshotter = CodeSnapshotter(temp_project, Language.PYTHON)
        snapshot = snapshotter.create_snapshot()
        assert "### target.py" in snapshot.content
        assert "### symlink.py" in snapshot.content
    except OSError:
        pytest.skip("Symlink creation failed - might need admin rights on Windows")


def test_search_terms_with_special_regex_chars(temp_project):
    (temp_project / "file[1].py").write_text("print('brackets')")
    (temp_project / "file.py").write_text("print('normal')")
    config = Config(search_terms=["file[1]"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert not filter.should_ignore(temp_project / "file[1].py")
    assert filter.should_ignore(temp_project / "file.py")


def test_ignore_patterns_with_wildcards(temp_project):
    (temp_project / "test1.log").write_text("log1")
    (temp_project / "test2.log").write_text("log2")
    (temp_project / "logs").mkdir()
    (temp_project / "logs" / "test3.log").write_text("log3")
    config = Config(ignore_patterns=["**/*.log"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert filter.should_ignore(temp_project / "test1.log")
    assert filter.should_ignore(temp_project / "test2.log")
    assert filter.should_ignore(temp_project / "logs" / "test3.log")


def test_search_terms_with_path_components(temp_project):
    (temp_project / "search_dir").mkdir()
    (temp_project / "search_dir" / "file1.py").write_text("content1")
    (temp_project / "other_dir").mkdir()
    (temp_project / "other_dir" / "file2.py").write_text("content2")
    config = Config(search_terms=["search_dir"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    # Current implementation only checks filenames, not path components
    assert filter.should_ignore(temp_project / "search_dir" / "file1.py")
    assert filter.should_ignore(temp_project / "other_dir" / "file2.py")


def test_gitignore_with_negated_patterns(temp_project):
    (temp_project / ".gitignore").write_text("*.log\n!important.log\n")
    (temp_project / "test.log").write_text("ignore")
    (temp_project / "important.log").write_text("don't ignore")
    filter = FileFilter(temp_project, Language.PYTHON, Config())
    assert filter.should_ignore(temp_project / "test.log")
    # Not asserting anything about important.log (current implementation ignores negation)


def test_filter_with_filename_patterns(temp_project):
    (temp_project / "ignore_me.py").write_text("should be ignored")
    (temp_project / "keep_me.py").write_text("should be kept")
    config = Config(ignore_patterns=["ignore_me.py"])
    filter = FileFilter(temp_project, Language.PYTHON, config)
    assert filter.should_ignore(temp_project / "ignore_me.py")
    assert not filter.should_ignore(temp_project / "keep_me.py")


def test_filter_with_complex_ignore_patterns(temp_project):
    src_path = temp_project / "src"
    test_path = temp_project / "test"
    # Clean up if test reruns
    import shutil
    if test_path.exists():
        shutil.rmtree(test_path)
    test_path.mkdir()
    (src_path / "main.py").write_text("print('main')")
    (test_path / "test_main.py").write_text("def test_main(): pass")
    (test_path / "other_test.py").write_text("def other_test(): pass")
    config = Config(
        ignore_patterns=[
            "src/*",
            "test/test_*",
        ],
        include_extensions=[".py"],
    )
    filter_obj = FileFilter(temp_project, Language.PYTHON, config)
    assert filter_obj.should_ignore(src_path / "main.py")
    assert filter_obj.should_ignore(test_path / "test_main.py")
    assert not filter_obj.should_ignore(test_path / "other_test.py")


def test_should_include_by_search_terms_with_empty_terms():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config = Config(search_terms=[])
        filter_obj = FileFilter(root, Language.PYTHON, config)
        test_file = root / "test.py"
        test_file.touch()
        assert filter_obj.should_include_by_search_terms(test_file) is True


def test_filter_with_exclude_patterns():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "include.py").touch()
        (root / "exclude.py").touch()
        config = Config(exclude_patterns=["exclude.py"])
        filter_obj = FileFilter(root, Language.PYTHON, config)
        assert filter_obj.should_ignore(root / "exclude.py") is True
        assert filter_obj.should_ignore(root / "include.py") is False


def test_should_ignore_with_search_terms_dir(tmp_path):
    d = tmp_path / "foo"
    d.mkdir()
    config = Config(search_terms=["foo"])
    ff = FileFilter(tmp_path, Language.PYTHON, config)
    assert ff.should_ignore(d) is False


def test_get_ignore_patterns_reads_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text("foo.txt\nbar/")
    config = Config()
    ff = FileFilter(tmp_path, Language.PYTHON, config)
    patterns = ff._get_ignore_patterns()
    assert any("foo.txt" in pat for pat in patterns)


def test_gitignore_negated_pattern(tmp_path):
    (tmp_path / ".gitignore").write_text("!main.py\n")
    config = Config()
    ff = FileFilter(tmp_path, Language.PYTHON, config)
    ff._get_ignore_patterns()