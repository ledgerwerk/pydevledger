from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from packaging.utils import canonicalize_name

from .types import InstalledDistribution, Project

_INSPECT_SCRIPT = r'''
import importlib.metadata as md
import json

rows = []
for dist in md.distributions():
    name = dist.metadata.get("Name")
    if not name:
        continue
    direct = None
    try:
        raw = dist.read_text("direct_url.json")
        if raw:
            direct = json.loads(raw)
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    rows.append({
        "name": name,
        "version": dist.version,
        "direct_url": direct,
    })
print(json.dumps(rows))
'''


def venv_python(path: Path) -> Path | None:
    path = path.expanduser()
    if path.is_file():
        return path.resolve()
    if not path.is_dir():
        return None
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidate = path / relative
    return candidate.resolve() if candidate.is_file() else None


def resolve_python(explicit: Path | None = None, *, root: Path | None = None) -> Path:
    if explicit is not None:
        candidate = venv_python(explicit)
        if candidate is None:
            raise RuntimeError(f"Python interpreter does not exist: {explicit.expanduser()}")
        return candidate

    active = os.environ.get("VIRTUAL_ENV")
    if active:
        candidate = venv_python(Path(active))
        if candidate is not None:
            return candidate

    if root is not None:
        candidate = venv_python(root.expanduser().resolve() / ".venv")
        if candidate is not None:
            return candidate

    candidate = Path(sys.executable).resolve()
    if not candidate.is_file():
        raise RuntimeError(f"Python interpreter does not exist: {candidate}")
    return candidate


def inspect_environment(python: Path) -> dict[str, InstalledDistribution]:
    python = python.expanduser().resolve()
    if not python.is_file():
        raise RuntimeError(f"Python interpreter does not exist: {python}")
    result = subprocess.run(
        [str(python), "-c", _INSPECT_SCRIPT],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"Cannot inspect environment with {python}: {result.stderr.strip()}"
        )

    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Cannot inspect environment with {python}: invalid JSON") from exc

    installed: dict[str, InstalledDistribution] = {}
    for row in rows:
        source = None
        editable = False
        direct = row.get("direct_url")
        if isinstance(direct, dict):
            url = direct.get("url")
            editable = bool((direct.get("dir_info") or {}).get("editable"))
            if isinstance(url, str) and url.startswith("file://"):
                from urllib.parse import unquote, urlparse

                parsed = urlparse(url)
                source = Path(unquote(parsed.path)).resolve()

        key = canonicalize_name(row["name"])
        installed[key] = InstalledDistribution(
            name=row["name"],
            key=key,
            version=row["version"],
            editable=editable,
            source=source,
        )

    return installed


def classify_project_install(
    project: Project,
    distribution: InstalledDistribution | None,
) -> str:
    if distribution is None:
        return "MISSING"
    if distribution.source is None:
        return "NON-LOCAL"
    if distribution.source != project.path.resolve():
        return "WRONG-SOURCE"
    return "OK" if distribution.editable else "LOCAL-NONEDIT"
