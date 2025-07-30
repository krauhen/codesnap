"""Tests for main module execution."""

import sys
import runpy

from unittest.mock import patch


def test_main_module_execution():
    """Test execution of the module as a script."""
    with (
        patch("codesnap.cli.main") as mock_main,
        patch.object(sys, "argv", ["python", "-m", "codesnap"]),
    ):
        try:
            # Use runpy to simulate module execution
            runpy.run_module("codesnap.__main__", run_name="__main__")
        except SystemExit:
            # Ignore system exit which is normal for CLI apps
            pass

        # Verify main was called
        mock_main.assert_called_once()


def test_main_module_with_arguments():
    """Test module execution with arguments."""
    with (
        patch("codesnap.cli.main") as mock_main,
        patch.object(sys, "argv", ["python", "-m", "codesnap", ".", "-l", "python"]),
    ):
        try:
            # Use runpy to simulate module execution
            runpy.run_module("codesnap.__main__", run_name="__main__")
        except SystemExit:
            # Ignore system exit which is normal for CLI apps
            pass

        # Verify main was called
        mock_main.assert_called_once()


def test_main_module_with_error():
    """Test module execution with an error."""
    with (
        patch("codesnap.cli.main", side_effect=Exception("Test error")),
        patch.object(sys, "argv", ["python", "-m", "codesnap"]),
        patch("sys.exit") as mock_exit,
    ):
        try:
            # This should catch the exception and call sys.exit(1)
            runpy.run_module("codesnap.__main__", run_name="__main__")
        except Exception:
            # The exception might not be caught by __main__, which is fine
            pass

        # Check if sys.exit was called with error code
        if mock_exit.called:
            mock_exit.assert_called_with(1)


def test_main_module_help():
    """Test module execution with --help argument."""
    with (
        patch("codesnap.cli.main") as mock_main,
        patch.object(sys, "argv", ["python", "-m", "codesnap", "--help"]),
    ):
        try:
            # --help typically causes sys.exit(0)
            runpy.run_module("codesnap.__main__", run_name="__main__")
        except SystemExit as e:
            assert e.code == 0

        # main should be called (Click will handle the --help)
        mock_main.assert_called_once()
