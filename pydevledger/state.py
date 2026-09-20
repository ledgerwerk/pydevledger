from __future__ import annotations

import json
from pathlib import Path

STATE_DIR = ".pydevledger"
STATE_FILE = "state.json"


def load_state(root: Path) -> dict[str, str]:
    path = root / STATE_DIR / STATE_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    seen = data.get("seen_releases", {})
    return (
        {str(key): str(value) for key, value in seen.items()}
        if isinstance(seen, dict)
        else {}
    )


def save_state(root: Path, seen_releases: dict[str, str]) -> None:
    directory = root / STATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / STATE_FILE
    payload = {"seen_releases": dict(sorted(seen_releases.items()))}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
