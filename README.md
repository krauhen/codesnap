# usage
## setup
```bash
$ uv venv .venv
$ source .venv/bin/activate
$ uv sync
$ codesnap --help
```

## examples
```bash
$ codesnap codesnap --language python --clipboard
✓ Snapshot copied to clipboard.
```
```bash
$ codesnap codesnap --language python
Project: codesnap
Language: python
Root: /Users/use/Repositories/codesnap/codesnap

File Contents:

Directory Structure:

codesnap/
    |-- __init__.py
    |-- __main__.py
    |-- analyzer.py
...
```

# dev
## test
```bash
$ uv run coverage run -m pytest
```