from pathlib import Path

from pydevledger.config import DiscoveryConfig, DEFAULT_EXCLUDED_NAMES
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


def test_exclusions_prune_names_and_paths_without_prefix_overmatch(tmp_path: Path) -> None:
    write_project(tmp_path / "generated" / "internal", "generated-project")
    write_project(tmp_path / "clients" / "acme" / "old", "old-project")
    write_project(tmp_path / "clients" / "acme" / "old-new", "new-project")
    config = DiscoveryConfig(
        exclude_names=DEFAULT_EXCLUDED_NAMES | {"generated"},
        exclude_paths=("clients/acme/old",),
    )

    projects = discover(tmp_path, config=config)

    assert set(projects) == {"new-project"}


def test_excluded_duplicate_does_not_trigger_duplicate_error(tmp_path: Path) -> None:
    write_project(tmp_path / "included", "same-name")
    write_project(tmp_path / "archive" / "excluded", "same-name")
    config = DiscoveryConfig(
        exclude_names=DEFAULT_EXCLUDED_NAMES,
        exclude_paths=("archive",),
    )

    projects = discover(tmp_path, config=config)

    assert set(projects) == {"same-name"}


def test_hidden_directories_and_git_remain_excluded(tmp_path: Path) -> None:
    write_project(tmp_path / ".hidden" / "project", "hidden-project")
    write_project(tmp_path / ".git" / "project", "git-project")

    assert discover(tmp_path) == {}
    config = DiscoveryConfig(
        exclude_names=DEFAULT_EXCLUDED_NAMES,
        exclude_paths=(),
        include_hidden=True,
    )
    projects = discover(tmp_path, config=config)
    assert set(projects) == {"hidden-project"}
