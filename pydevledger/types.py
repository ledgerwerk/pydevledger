from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from packaging.requirements import Requirement


@dataclass(slots=True)
class Project:
    name: str
    key: str
    path: Path
    git_root: Path
    dependencies: list[Requirement] = field(default_factory=list)
    local_dependencies: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InstalledDistribution:
    name: str
    key: str
    version: str
    editable: bool = False
    source: Path | None = None


@dataclass(slots=True)
class DependencyUse:
    dependency: str
    requirement: Requirement
    project: Project


@dataclass(slots=True)
class ReleaseStatus:
    dependency: str
    installed: str | None
    latest_compatible: str | None
    latest_upstream: str | None
    consumers: list[DependencyUse]
    is_new: bool = False
