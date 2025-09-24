"""Tests for core functionality (aligned with simplified codesnap.core)."""
import tempfile
import time
import os
import pytest
import tiktoken
import threading
from pathlib import Path

from codesnap.config import Config, Language
from codesnap.core import CodeSnapshotter, Snapshot
from codesnap.formatters import SnapshotFormatter, OutputFormat


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create a minimal project
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text("def hello():\n    print('Hello, world!')\n")
        (root / "src" / "__init__.py").write_text("")
        (root / "tests").mkdir()
        (root / "tests" / "test_main.py").write_text("def test_hello():\n    pass\n")
        (root / "README.md").write_text("# Test Project\n")
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        yield root


def test_create_snapshot_basic(temp_project):
    snapper = CodeSnapshotter(temp_project, Language.PYTHON)
    snap = snapper.create_snapshot()
    assert isinstance(snap, Snapshot)
    # At least README, main.py, test_main.py, pyproject and init
    assert snap.file_count >= 5
    assert "# Test Project" in snap.content
    assert "def hello():" in snap.content


def test_create_snapshot_with_and_without_tree(temp_project):
    snapper = CodeSnapshotter(temp_project, Language.PYTHON)
    snap = snapper.create_snapshot(show_tree=True)
    assert "Directory Structure" in snap.content
    snap2 = snapper.create_snapshot(show_tree=False)
    assert "Directory Structure" not in snap2.content


def test_file_sorting(temp_project):
    snapper = CodeSnapshotter(temp_project, Language.PYTHON)
    files = snapper._collect_files()
    sorted_files = snapper._sort_files(files)
    assert sorted_files  # not empty
    # important files early
    assert sorted_files[0].name in ("pyproject.toml", "requirements.txt", "setup.py", "package.json")


def test_custom_config(temp_project):
    config = Config(ignore_patterns=["tests/"], include_extensions=[".py", ".md"])
    snapper = CodeSnapshotter(temp_project, Language.PYTHON, config)
    snap = snapper.create_snapshot()
    assert "test_main.py" not in snap.content
    assert "main.py" in snap.content
    assert "README.md" in snap.content


def test_empty_file_handling(temp_project):
    (temp_project / "empty.py").write_text("")
    snapper = CodeSnapshotter(temp_project, Language.PYTHON)
    snap = snapper.create_snapshot()
    assert "### empty.py" in snap.content


def test_empty_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        snapper = CodeSnapshotter(Path(tmpdir), Language.PYTHON)
        snap = snapper.create_snapshot()
        assert isinstance(snap, Snapshot)
        # file_count may be 0, but output should not be crashing
        assert isinstance(snap.file_count, int)


def test_concurrent_file_access(temp_project):
    test_file = temp_project / "concurrent.py"
    test_file.write_text("# Initial content")

    def modify_file():
        time.sleep(0.05)
        test_file.write_text("# Modified content")

    t = threading.Thread(target=modify_file)
    t.start()
    snapper = CodeSnapshotter(temp_project, Language.PYTHON)
    snap = snapper.create_snapshot()
    t.join()
    assert "concurrent.py" in snap.content


def test_snapshot_with_no_files(temp_project):
    config = Config(ignore_patterns=["*"])
    snapper = CodeSnapshotter(temp_project, Language.PYTHON, config)
    snap = snapper.create_snapshot()
    assert snap.file_count == 0


def test_snapshot_with_invalid_encoding(temp_project):
    with pytest.raises(ValueError):
        CodeSnapshotter(temp_project, Language.PYTHON, model_encoding="non_existent")


def test_snapshot_without_token_counting(temp_project):
    snapper = CodeSnapshotter(temp_project, Language.PYTHON, count_tokens=False)
    snap = snapper.create_snapshot()
    assert snap.token_count == 0


def test_json_output_format(temp_project):
    snapper = CodeSnapshotter(temp_project, Language.PYTHON)
    snap = snapper.create_snapshot(output_format=OutputFormat.JSON)
    import json
    data = json.loads(snap.content)
    assert "project" in data
    assert "language" in data
    assert "files" in data


def test_build_tree_handles_permission_error(tmp_path, monkeypatch):
    cs = CodeSnapshotter(tmp_path, Language.PYTHON)
    d = tmp_path / "dir"
    d.mkdir()
    real_iterdir = Path.iterdir

    def perm_error(self):
        raise PermissionError("No access")

    monkeypatch.setattr(Path, "iterdir", perm_error)
    cs._build_tree()
    monkeypatch.setattr(Path, "iterdir", real_iterdir)


def test_count_tokens_accuracy():
    snapper = CodeSnapshotter(Path("/tmp"), Language.PYTHON, model_encoding="cl100k_base")
    s = "def foo():\n    return 1"
    c = snapper._count_tokens(s)
    tok = tiktoken.get_encoding("cl100k_base")
    assert c == len(tok.encode(s))