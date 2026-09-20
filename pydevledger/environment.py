from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from packaging.utils import canonicalize_name

from .types import InstalledDistribution

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


def resolve_python(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()

    active = os.environ.get("VIRTUAL_ENV")
    if active:
        if os.name == "nt":
            candidate = Path(active) / "Scripts" / "python.exe"
        else:
            candidate = Path(active) / "bin" / "python"
        if candidate.is_file():
            return candidate.resolve()

    return Path(sys.executable).resolve()


def inspect_environment(python: Path) -> dict[str, InstalledDistribution]:
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

    installed: dict[str, InstalledDistribution] = {}
    for row in json.loads(result.stdout):
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
