# pydevledger

`pydevledger` is an MVP for keeping a Python development environment aligned with a set of checked-out Git repositories.

It answers four questions:

1. Which Git checkouts below this directory contain installable `pyproject.toml` projects?
2. Which of those projects are installed in this Python environment, and are they editable from the expected checkout?
3. Which local projects depend on a given package?
4. Which direct dependencies have newer releases on PyPI, and which releases still satisfy the declared constraints?

It deliberately does **not** resolve dependencies itself. `uv` remains the installer/resolver.

## Layout

There is intentionally no `src/` layer:

```text
pydevledger/
  __init__.py
  cli.py
  discovery.py
  environment.py
  releases.py
  state.py
  types.py
tests/
pyproject.toml
```

## Dynamic versioning

Versions come from Git tags through `setuptools-scm`.

```bash
git init
git add .
git commit -m "Initial MVP"
git tag v0.1.0
python -m pip install -e .
pydevledger --version
```

A source tree without Git metadata falls back to `0.0.0`, which keeps unpacked archives installable.

## Quick start

```bash
python -m pip install -e .

# Discover Python projects in Git worktrees.
pydevledger --root ~/code scan

# Compare them with the selected Python environment.
pydevledger --root ~/code --python /path/to/.venv/bin/python status

# Show all local projects declaring a dependency on pydantic.
pydevledger --root ~/code dependents pydantic

# Check direct dependencies against PyPI.
pydevledger --root ~/code --python /path/to/.venv/bin/python updates

# Record the currently observed upstream releases as acknowledged.
pydevledger --root ~/code updates --ack

# Install every discovered project editable in one uv transaction.
pydevledger --root ~/code --python /path/to/.venv/bin/python sync
```

If `--python` is omitted, `pydevledger` uses `$VIRTUAL_ENV/bin/python` when available, otherwise the interpreter running `pydevledger`.

## Current MVP boundaries

- PyPI is the only release source.
- Only PEP 621 `[project]` metadata is read.
- Dependency groups / extras are not scanned yet.
- `updates` checks declared direct dependencies, not the full resolved transitive graph.
- Release compatibility currently means the declared version specifier; `Requires-Python`, platform markers, and lockfiles are future work.
- Git metadata is used for project discovery but commit/dirty-state reporting is not yet persisted in the ledger.
