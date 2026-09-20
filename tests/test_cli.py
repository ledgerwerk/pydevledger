from pathlib import Path

import pytest

from pydevledger.cli import main



def write_project(path: Path, name: str) -> None:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )


def test_scan_uses_workspace_config_and_cli_exclude(tmp_path: Path, capsys) -> None:
    write_project(tmp_path / "included", "included")
    write_project(tmp_path / "configured", "configured")
    write_project(tmp_path / "temporary", "temporary")
    (tmp_path / ".pydevledger.toml").write_text(
        'schema_version = 1\n[discovery]\nexclude_paths = ["configured"]\n',
        encoding="utf-8",
    )

    assert main(["--root", str(tmp_path), "--exclude", "temporary", "scan"]) == 0
    output = capsys.readouterr().out
    assert "included" in output
    assert "configured" not in output
    assert "temporary" not in output


def test_sync_dry_run_uses_configured_project_set(tmp_path: Path, monkeypatch, capsys) -> None:
    write_project(tmp_path / "a", "a")
    write_project(tmp_path / "b", "b")
    (tmp_path / ".pydevledger.toml").write_text(
        'schema_version = 1\n[discovery]\nexclude_paths = ["b"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/usr/bin/uv")

    assert main(["--root", str(tmp_path), "sync", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "/a" in output
    assert f"-e {tmp_path / 'b'}" not in output


def test_missing_explicit_config_is_cli_error(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--root", str(tmp_path), "--config", str(tmp_path / "missing"), "scan"])
    assert exc_info.value.code == 2
    assert "does not exist" in capsys.readouterr().err
