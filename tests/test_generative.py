# tests/test_generative.py

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


# ---- CLI Smoke Tests ----


@pytest.mark.parametrize(
    "cli_args, expected",
    [
        (["-l", "python"], "# Project:"),  # default markdown output
        (["-l", "python", "--output-format", "text"], "Project:"),  # plain text format
        (["-l", "python", "--output-format", "json"], '"project"'),  # JSON format
        (["-l", "python", "--no-tree"], "File Contents"),  # tree skipped
        (["-l", "python", "--max-tokens", "50"], "stopped"),  # token truncation
        (["-l", "python", "--no-header", "--no-footer"], "def foo"),  # content only
    ],
)
def test_cli_on_python_sandbox(python_sandbox, cli_args, expected):
    """
    Run codesnap.cli.main on the synthetic project with various flags and
    verify the output matches expectations.
    """
    runner = CliRunner()
    result = runner.invoke(main, [str(python_sandbox)] + cli_args)
    assert result.exit_code == 0
    assert expected in result.output


def test_cli_hidden_files_are_included_by_default(python_sandbox):
    """Check that hidden files are included unless excluded manually."""
    runner = CliRunner()
    result = runner.invoke(main, [str(python_sandbox), "-l", "python"])
    # secret.py is actually included
    assert "secret.py" in result.output

    # But if we exclude hidden dir explicitly, it should be filtered out
    result = runner.invoke(main, [str(python_sandbox), "-l", "python", "--exclude", ".hidden/*"])
    assert "secret.py" not in result.output
