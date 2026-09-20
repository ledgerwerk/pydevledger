from __future__ import annotations

import os
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from .types import DependencyUse, Project

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "solution",
    "starting_code",
}


def _git_root(path: Path, boundary: Path) -> Path | None:
    current = path
    boundary = boundary.resolve()
    while True:
        if (current / ".git").exists():
            return current
        if current == boundary or current.parent == current:
            return None
        current = current.parent


def discover(root: Path) -> dict[str, Project]:
    root = root.resolve()
    projects: dict[str, Project] = {}

    for directory, directories, files in os.walk(root):
        current = Path(directory)
        directories[:] = [
            name
            for name in directories
            if name not in EXCLUDED_DIRS and not name.startswith(".")
        ]

        if "pyproject.toml" not in files:
            continue

        git_root = _git_root(current, root)
        if git_root is None:
            continue

        manifest = current / "pyproject.toml"
        try:
            with manifest.open("rb") as stream:
                metadata = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise RuntimeError(f"Cannot read {manifest}: {exc}") from exc

        project_metadata = metadata.get("project")
        if not isinstance(project_metadata, dict) or not project_metadata.get("name"):
            continue

        name = str(project_metadata["name"])
        key = canonicalize_name(name)
        if key in projects:
            other = projects[key]
            raise RuntimeError(
                f"Duplicate local project name {name!r}: {other.path} and {current}"
            )

        requirements: list[Requirement] = []
        for raw in project_metadata.get("dependencies", []):
            try:
                requirements.append(Requirement(str(raw)))
            except InvalidRequirement as exc:
                raise RuntimeError(
                    f"Invalid requirement in {manifest}: {raw!r}: {exc}"
                ) from exc

        projects[key] = Project(
            name=name,
            key=key,
            path=current.resolve(),
            git_root=git_root.resolve(),
            dependencies=requirements,
        )

    for project in projects.values():
        for requirement in project.dependencies:
            dependency_key = canonicalize_name(requirement.name)
            if dependency_key in projects and dependency_key != project.key:
                project.local_dependencies.append(dependency_key)

    return projects


def dependency_uses(projects: dict[str, Project]) -> dict[str, list[DependencyUse]]:
    uses: dict[str, list[DependencyUse]] = {}
    for project in projects.values():
        for requirement in project.dependencies:
            key = canonicalize_name(requirement.name)
            uses.setdefault(key, []).append(
                DependencyUse(dependency=key, requirement=requirement, project=project)
            )
    return uses
