"""Entry point for the codesnap package when run as a module."""

from codesnap.cli import main


def _run_main():
    """Wrapper to ensure main is called."""
    main()


if __name__ == "__main__":
    _run_main()
