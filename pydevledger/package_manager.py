from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .config import PackageManagerConfig
from .types import Project
from .uv import UvPackageManager

SUPPORTED_PACKAGE_MANAGERS = frozenset({"uv"})


class PackageManager(Protocol):
    name: str

    def sync(
        self, python: Path, projects: list[Project], *, dry_run: bool = False
    ) -> int: ...

    def check(self, python: Path) -> int: ...


def get_package_manager(config: PackageManagerConfig) -> PackageManager:
    if config.system not in SUPPORTED_PACKAGE_MANAGERS:
        supported = ", ".join(sorted(SUPPORTED_PACKAGE_MANAGERS))
        raise RuntimeError(
            f"Unsupported package manager {config.system!r}; supported: {supported}"
        )
    return UvPackageManager(config.uv)
