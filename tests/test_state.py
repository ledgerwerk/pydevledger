from pathlib import Path

from pydevledger.state import load_state, save_state


def test_state_roundtrip_is_sorted_and_compatible(tmp_path: Path) -> None:
    save_state(tmp_path, {"zeta": "1.0", "requests": "2.33.0"})
    assert load_state(tmp_path) == {"requests": "2.33.0", "zeta": "1.0"}
    assert '"seen_releases"' in (tmp_path / ".pydevledger" / "state.json").read_text()


def test_missing_and_malformed_state_are_empty(tmp_path: Path) -> None:
    assert load_state(tmp_path) == {}
    path = tmp_path / ".pydevledger" / "state.json"
    path.parent.mkdir()
    path.write_text("not-json", encoding="utf-8")
    assert load_state(tmp_path) == {}


def test_wrong_state_shape_is_empty(tmp_path: Path) -> None:
    path = tmp_path / ".pydevledger" / "state.json"
    path.parent.mkdir()
    path.write_text('{"seen_releases": ["bad"]}', encoding="utf-8")
    assert load_state(tmp_path) == {}
