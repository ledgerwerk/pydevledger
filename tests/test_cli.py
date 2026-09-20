from pathlib import Path

import pytest

from pydevledger.cli import main


def write_project(path: Path, name: str, dependencies: list[str] | None = None) -> None:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    dependency_lines = "\n".join(f'  "{item}",' for item in dependencies or [])
    dependency_block = (
        f"dependencies = [\n{dependency_lines}\n]"
        if dependency_lines
        else "dependencies = []"
    )
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n{dependency_block}\n',
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


def test_sync_dry_run_uses_configured_project_set(
    tmp_path: Path, monkeypatch, capsys
) -> None:
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


def test_sync_exclusion_keeps_project_visible_but_omits_editable(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    write_project(tmp_path / "a", "a")
    write_project(tmp_path / "g2lex-data", "g2lex-data")
    (tmp_path / ".pydevledger.toml").write_text(
        'schema_version = 2\n[sync]\nexclude_paths = ["g2lex-data"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/usr/bin/uv")

    assert main(["--root", str(tmp_path), "scan"]) == 0
    scan_output = capsys.readouterr().out
    assert "a" in scan_output
    assert "g2lex-data" in scan_output

    assert main(["--root", str(tmp_path), "sync", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert f"-e {tmp_path / 'a'}" in output
    assert f"-e {tmp_path / 'g2lex-data'}" not in output
    assert "Skipping sync-excluded projects:" in output
    assert "g2lex-data" in output


def test_all_sync_excluded_is_successful_no_op(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    write_project(tmp_path / "a", "a")
    (tmp_path / ".pydevledger.toml").write_text(
        'schema_version = 2\n[sync]\nexclude_paths = ["a"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pydevledger.uv.subprocess.run",
        lambda *args, **kwargs: pytest.fail(
            "uv should not run for an empty sync selection"
        ),
    )

    assert main(["--root", str(tmp_path), "sync"]) == 0
    output = capsys.readouterr().out
    assert "No projects selected for sync." in output


def test_nested_sync_exclusion_uses_path_components(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    write_project(tmp_path / "experiments" / "a", "a")
    write_project(tmp_path / "experiments" / "group" / "b" / "tool", "tool")
    write_project(tmp_path / "experiments-new" / "c", "c")
    (tmp_path / ".pydevledger.toml").write_text(
        'schema_version = 2\n[sync]\nexclude_paths = ["experiments"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/usr/bin/uv")

    assert main(["--root", str(tmp_path), "sync", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert f"-e {tmp_path / 'experiments-new' / 'c'}" in output
    assert f"-e {tmp_path / 'experiments' / 'a'}" not in output
    assert f"-e {tmp_path / 'experiments' / 'group' / 'b' / 'tool'}" not in output


def test_sync_warns_when_selected_project_depends_on_skipped_local_project(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    write_project(tmp_path / "a", "a", ["g2lex-data>=1"])
    write_project(tmp_path / "g2lex-data", "g2lex-data")
    (tmp_path / ".pydevledger.toml").write_text(
        'schema_version = 2\n[sync]\nexclude_paths = ["g2lex-data"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/usr/bin/uv")

    assert main(["--root", str(tmp_path), "sync", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "WARNING: a declares g2lex-data>=1" in output
    assert "uv may still resolve the package as a dependency." in output
    assert f"-e {tmp_path / 'g2lex-data'}" not in output


def test_missing_explicit_config_is_cli_error(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--root", str(tmp_path), "--config", str(tmp_path / "missing"), "scan"])
    assert exc_info.value.code == 2
    assert "does not exist" in capsys.readouterr().err
