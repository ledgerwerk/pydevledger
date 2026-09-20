from pathlib import Path

from pydevledger.state import load_state, save_state


def test_state_roundtrip(tmp_path: Path) -> None:
    save_state(tmp_path, {"requests": "2.33.0"})
    assert load_state(tmp_path) == {"requests": "2.33.0"}
