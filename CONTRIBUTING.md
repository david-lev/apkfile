🤝 **Contributing**
--------------------

Thank you for considering contributing to apkfile! This guide walks you through the steps and standards to
follow.

## Prerequisites

- [Python](https://www.python.org/downloads/) 3.10 or higher
- [uv](https://docs.astral.sh/uv/) for dependency management and virtual environments
- A [GitHub account](https://github.com)
- Familiarity with [git](https://git-scm.com/) for version control

## Getting started

1. **Fork** the repository and **clone** your fork locally:

   ```bash
   git clone https://github.com/<your-username>/apkfile.git
   cd apkfile
   ```

2. Sync the virtual environment and install the required dependencies:

   ```bash
   uv sync
   ```

3. Activate [pre-commit](https://pre-commit.com/) to ensure code quality:

   ```bash
   uv run pre-commit install
   ```

4. Run the tests to make sure everything is working:

   ```bash
   uv run pytest
   ```

## Common commands

```bash
uv run pytest                       # full test suite
uv run pytest tests/test_apk.py     # one file
uv run pytest -k test_name          # one test

uv run ruff check .                 # lint
uv run ruff format .                # format
uv run ty check                     # type check
uv run pre-commit run --all-files   # everything pre-commit enforces
```

## Submitting changes

1. Create a branch for your change.
2. Make your change, with tests where it makes sense.
3. Make sure `uv run pre-commit run --all-files` passes.
4. Open a pull request describing what changed and why.
