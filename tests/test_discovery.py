from pathlib import Path

from pydevledger.discovery import dependency_uses, discover


def write_project(path: Path, name: str, dependencies: list[str] | None = None) -> None:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    deps = dependencies or []
    dep_lines = ",\n  ".join(repr(item) for item in deps)
    (path / "pyproject.toml").write_text(
        f'''[project]\nname = "{name}"\nversion = "0.1.0"\ndependencies = [\n  {dep_lines}\n]\n''',
        encoding="utf-8",
    )


def test_discover_local_dependency(tmp_path: Path) -> None:
    write_project(tmp_path / "a", "tool-a", ["tool-b>=1", "requests>=2"])
    write_project(tmp_path / "b", "tool-b")

    projects = discover(tmp_path)

    assert set(projects) == {"tool-a", "tool-b"}
    assert projects["tool-a"].local_dependencies == ["tool-b"]
    uses = dependency_uses(projects)
    assert {use.project.name for use in uses["tool-b"]} == {"tool-a"}
