import shutil
import pytest
from click.testing import CliRunner
from codesnap.cli import main

@pytest.fixture
def python_sandbox(tmp_path):
    """
    Create a deterministic Python package structure with multiple layers,
    hidden files, and a tricky substructure.
    Cleans up afterwards.
    """
    root = tmp_path / "py_sandbox"
    root.mkdir()
    # top-level project files
    (root / "README.md").write_text("# Python Sandbox\n")
    (root / ".gitignore").write_text("__pycache__/\n")
    (root / "setup.py").write_text("from setuptools import setup; setup()\n")
    # package
    pkg = root / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# package init\n")
    (pkg / "module.py").write_text("def foo():\n    return 'bar'\n")
    # subpackage
    subpkg = pkg / "subpackage"
    subpkg.mkdir()
    (subpkg / "__init__.py").write_text("# subpackage init\n")
    (subpkg / "util.py").write_text("def util():\n    return 42\n")
    # hidden dir + file
    hidden = root / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text("password = 'hunter2'\n")
    # nested deeper structure
    deep = root / "deep" / "deeper" / "deepest"
    deep.mkdir(parents=True)
    (deep / "deep_module.py").write_text("def deep():\n    return 'deep'\n")
    yield root
    shutil.rmtree(root)

@pytest.mark.parametrize(
    "rel_path, expected_snippet",
    [
        ("README.md", "# Python Sandbox"),
        (".gitignore", "__pycache__"),
        ("setup.py", "setuptools"),
        ("mypackage/__init__.py", "package init"),
        ("mypackage/module.py", "def foo"),
        ("mypackage/subpackage/__init__.py", "subpackage init"),
        ("mypackage/subpackage/util.py", "def util"),
        (".hidden/secret.py", "password = 'hunter2'"),
        ("deep/deeper/deepest/deep_module.py", "def deep"),
    ],
)
def test_python_sandbox_files_exist_and_content(python_sandbox, rel_path, expected_snippet):
    """Check that all known files exist and contain expected text."""
    file_path = python_sandbox / rel_path
    assert file_path.exists(), f"Expected {file_path} to exist"
    content = file_path.read_text()
    assert expected_snippet in content

def test_cli_generates_snapshot_markdown_by_default(python_sandbox):
    runner = CliRunner()
    result = runner.invoke(main, [str(python_sandbox), "-l", "python"])
    assert result.exit_code == 0
    assert "# Python Sandbox" in result.output
    assert "def foo" in result.output
    assert "Directory Structure" in result.output
    assert "File Contents" in result.output

def test_cli_hidden_files_are_included_by_default(python_sandbox):
    runner = CliRunner()
    result = runner.invoke(main, [str(python_sandbox), "-l", "python"])
    assert "secret.py" in result.output
    # Exclude hidden explicitly
    result2 = runner.invoke(main, [str(python_sandbox), "-l", "python", "--exclude", ".hidden/*"])
    assert "secret.py" not in result2.output