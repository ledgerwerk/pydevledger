import json
from pathlib import Path
from types import SimpleNamespace

from pydevledger.environment import (
    classify_project_install,
    inspect_environment,
    resolve_python,
    venv_python,
)
from pydevledger.types import InstalledDistribution, Project


def make_python(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def test_resolution_prefers_explicit_then_active_then_root_venv(tmp_path: Path, monkeypatch) -> None:
    explicit = make_python(tmp_path / "explicit")
    active = make_python(tmp_path / "active" / "bin" / "python")
    root_python = make_python(tmp_path / ".venv" / "bin" / "python")
    monkeypatch.setenv("VIRTUAL_ENV", str(active.parent.parent))

    assert resolve_python(explicit, root=tmp_path) == explicit.resolve()
    assert resolve_python(root=tmp_path) == active.resolve()

    monkeypatch.delenv("VIRTUAL_ENV")
    assert resolve_python(root=tmp_path) == root_python.resolve()


def test_venv_python_and_missing_explicit(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    python = make_python(venv / "bin" / "python")
    assert venv_python(venv) == python.resolve()
    assert venv_python(tmp_path / "missing") is None


def test_classify_provenance_states(tmp_path: Path) -> None:
    project = Project(name="demo", key="demo", path=tmp_path / "demo", git_root=tmp_path)
    expected = project.path.resolve()
    assert classify_project_install(project, None) == "MISSING"
    assert classify_project_install(
        project,
        InstalledDistribution("demo", "demo", "1.0", source=None),
    ) == "NON-LOCAL"
    assert classify_project_install(
        project,
        InstalledDistribution("demo", "demo", "1.0", editable=True, source=tmp_path / "other"),
    ) == "WRONG-SOURCE"
    assert classify_project_install(
        project,
        InstalledDistribution("demo", "demo", "1.0", editable=False, source=expected),
    ) == "LOCAL-NONEDIT"
    assert classify_project_install(
        project,
        InstalledDistribution("demo", "demo", "1.0", editable=True, source=expected),
    ) == "OK"


def test_inspection_parses_direct_url_and_normalizes_names(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source dir"
    payload = [
        {
            "name": "Demo-Package",
            "version": "1.2",
            "direct_url": {
                "url": f"file://{source.as_posix().replace(' ', '%20')}",
                "dir_info": {"editable": True},
            },
        },
        {"name": "Other", "version": "2.0", "direct_url": None},
    ]
    monkeypatch.setattr(
        "pydevledger.environment.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )

    installed = inspect_environment(make_python(tmp_path / "python"))

    assert installed["demo-package"].source == source.resolve()
    assert installed["demo-package"].editable is True
    assert installed["other"].source is None
