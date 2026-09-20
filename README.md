# pydevledger

`pydevledger` keeps one Python development environment aligned with a set of checked-out Git Python projects. It discovers installable projects, verifies editable-install provenance, installs selected checkouts with uv, maps dependency consumers, and reports newly published dependency releases.

The workspace is a parent directory of independent Git repositories; it does not need to be a Python or uv workspace itself.

## Development

The repository uses uv for its own development workflow:

```bash
uv sync --dev
uv run pytest
uv build
```

The package keeps a flat layout (there is no `src/` directory) and uses dynamic versions from Git tags through `setuptools-scm`.

## Workspace configuration

Configuration is optional. Without an explicit `--config`, pydevledger reads only `<root>/.pydevledger.toml` when that file exists. It never searches above `--root`.

```toml
schema_version = 2

[package_manager]
system = "uv"

[package_manager.uv]
link_mode = "copy"

[discovery]
exclude_names = [".tox", "generated"]
exclude_paths = [
  "archive",
  "clients/acme/retired-service",
]
include_hidden = false

[sync]
# Still discovered and tracked, but omitted from sync.
exclude_paths = ["g2lex-data"]
```

The selected package-management system is workspace policy. With `system = "uv"`, environment mutation and verification use only uv; pydevledger does not silently fall back to pip, Poetry, or another manager. The `uv pip ...` form is a uv command, not a direct invocation of pip.

Built-in exclusions (`.git`, `.venv`, `__pycache__`, build output, and similar directories) remain active. Configured `exclude_names` are additive. `discovery.exclude_paths` and repeatable command-line `--exclude` values are exact root-relative directory subtrees, not glob patterns; they make a subtree invisible to discovery and all subsequent analysis.

`sync.exclude_paths` is a separate policy. Its paths are still discovered, listed by `scan`, included in local dependency and release analysis, and available to `status`, but their checkouts are omitted from the editable operands passed to `uv pip install`. In other words: `discovery.exclude_paths` means "do not model this checkout"; `sync.exclude_paths` means "model it, but do not install the local checkout."

This is useful when a checked-out project cannot be installed into a selected or global/base Python environment (for example, because a compatible package version is unavailable) while the project should remain visible to workspace tracking. If an included project declares a dependency on a sync-excluded local project, uv may still try to resolve that package from configured indexes or the existing environment; pydevledger warns about this and does not rewrite dependencies or add `--no-deps`.

For a one-command exclusion:

```bash
uv run pydevledger --root ~/code --exclude scratch scan
```

## Commands

```bash
# Discover Git-backed Python projects.
uv run pydevledger --root ~/code scan

# Compare projects with the selected environment.
uv run pydevledger --root ~/code --python ~/venvs/dev/bin/python status

# The root .venv is used when --python and VIRTUAL_ENV are absent.
uv run pydevledger --root ~/code status

# Show local consumers of a dependency.
uv run pydevledger --root ~/code dependents pydantic

# Check direct dependencies against PyPI.
uv run pydevledger --root ~/code --python ~/venvs/dev/bin/python updates

# Acknowledge observed upstream releases.
uv run pydevledger --root ~/code updates --ack

# Install all included projects editable in one uv transaction, then run uv pip check.
uv run pydevledger --root ~/code --python ~/venvs/dev/bin/python sync

# Print the deterministic uv command without changing the environment.
uv run pydevledger --root ~/code --exclude archive sync --dry-run
```

Target Python resolution is: explicit `--python`, `$VIRTUAL_ENV`, `<root>/.venv`, then the interpreter running pydevledger. Read-only environment inspection uses `importlib.metadata` and `direct_url.json` so status can distinguish `MISSING`, `NON-LOCAL`, `WRONG-SOURCE`, `LOCAL-NONEDIT`, and `OK`.

## Release reports and state

`updates` keeps separate `installed`, `latest compatible`, and `latest upstream` values, and lists every local consumer and its declared requirement. It reports releases but does not edit manifests or automatically upgrade environments.

Observed releases remain backward-compatible in `<root>/.pydevledger/state.json`. Configuration is user-authored workspace policy in `.pydevledger.toml`; state is local observation data and is commonly ignored by Git.

## Boundaries

- PyPI is the only release source, and network responses are not required by the automated tests.
- Only PEP 621 `[project]` metadata and direct dependencies are inspected.
- uv is the only implemented package-manager backend; selection is explicit and has no fallback.
- Dependency groups, extras, transitive resolution, lockfile parsing, automatic constraint edits, automatic upgrades, Git fetch/pull, and arbitrary exclusion globs are out of scope.
- Ledgercore is not a runtime dependency; pydevledger remains independently bootstrappable.
