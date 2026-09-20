from pathlib import Path
from types import SimpleNamespace

import pytest

from pydevledger.config import UvConfig
from pydevledger.types import Project
from pydevledger.uv import UvPackageManager


def project(tmp_path: Path, name: str) -> Project:
    path = tmp_path / name
    path.mkdir()
    return Project(name=name, key=name, path=path, git_root=tmp_path)


def test_install_command_is_deterministic_and_uses_link_mode(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/bin/uv")
    manager = UvPackageManager(UvConfig(link_mode="copy"))
    projects = [project(tmp_path, "zeta"), project(tmp_path, "Alpha")]

    assert manager.install_command(Path("/venv/bin/python"), projects) == [
        "/bin/uv",
        "pip",
        "install",
        "--python",
        "/venv/bin/python",
        "--link-mode",
        "copy",
        "-e",
        str(tmp_path / "Alpha"),
        "-e",
        str(tmp_path / "zeta"),
    ]


def test_sync_merges_configured_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/bin/uv")
    monkeypatch.setenv("INHERITED", "yes")
    monkeypatch.setenv("CFLAGS", "host")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("pydevledger.uv.subprocess.run", run)
    manager = UvPackageManager(
        UvConfig(environment=(("CFLAGS", "termux-flags"), ("MATHLIB", "m")))
    )

    assert manager.sync(Path("/python"), [project(tmp_path, "a")]) == 0
    output = capsys.readouterr().out
    assert "termux-flags" not in output
    assert "MATHLIB" not in output

    install_env = calls[0][1]["env"]
    check_env = calls[1][1]["env"]
    assert isinstance(install_env, dict)
    assert install_env["INHERITED"] == "yes"
    assert install_env["CFLAGS"] == "termux-flags"
    assert install_env["MATHLIB"] == "m"
    assert check_env == install_env
    assert all(call[1]["shell"] is False for call in calls)


def test_no_environment_overrides_pass_none_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/bin/uv")
    envs: list[object] = []

    def run(command, **kwargs):
        envs.append(kwargs["env"])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("pydevledger.uv.subprocess.run", run)
    assert (
        UvPackageManager(UvConfig()).sync(Path("/python"), [project(tmp_path, "a")])
        == 0
    )
    assert envs == [None, None]


def test_dry_run_does_not_execute(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/bin/uv")
    run = lambda *args, **kwargs: pytest.fail(
        "subprocess should not run during dry-run"
    )
    monkeypatch.setattr("pydevledger.uv.subprocess.run", run)

    assert (
        UvPackageManager(UvConfig()).sync(
            Path("/python"), [project(tmp_path, "a")], dry_run=True
        )
        == 0
    )


def test_install_failure_skips_check(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/bin/uv")
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr("pydevledger.uv.subprocess.run", run)
    assert (
        UvPackageManager(UvConfig()).sync(Path("/python"), [project(tmp_path, "a")])
        == 7
    )
    assert len(calls) == 1
    assert calls[0][1:3] == ["pip", "install"]


def test_check_runs_after_successful_install_and_returns_check_status(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("pydevledger.uv.shutil.which", lambda name: "/bin/uv")
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0 if len(calls) == 1 else 3)

    monkeypatch.setattr("pydevledger.uv.subprocess.run", run)
    assert (
        UvPackageManager(UvConfig()).sync(Path("/python"), [project(tmp_path, "a")])
        == 3
    )
    assert calls[1] == ["/bin/uv", "pip", "check", "--python", "/python"]


def test_missing_uv_fails_without_fallback(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def which(name: str):
        calls.append(name)

    monkeypatch.setattr("pydevledger.uv.shutil.which", which)
    with pytest.raises(
        RuntimeError, match="Configured package manager 'uv' was not found"
    ):
        UvPackageManager(UvConfig()).sync(Path("/python"), [project(tmp_path, "a")])
    assert calls == ["uv"]
