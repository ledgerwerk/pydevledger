from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import UvConfig
from .types import Project


class UvPackageManager:
    name = "uv"

    def __init__(self, config: UvConfig) -> None:
        self.config = config

    def _environment(self) -> dict[str, str] | None:
        if not self.config.environment:
            return None
        environment = os.environ.copy()
        environment.update(dict(self.config.environment))
        return environment

    def _executable(self) -> str:
        executable = shutil.which("uv")
        if executable is None:
            raise RuntimeError("Configured package manager 'uv' was not found on PATH")
        return executable

    def install_command(self, python: Path, projects: list[Project]) -> list[str]:
        executable = self._executable()
        command = [
            executable,
            "pip",
            "install",
            "--python",
            str(python),
            "--link-mode",
            self.config.link_mode,
        ]
        for project in sorted(projects, key=lambda item: item.name.lower()):
            command.extend(["-e", str(project.path)])
        return command

    def check_command(self, python: Path) -> list[str]:
        return [self._executable(), "pip", "check", "--python", str(python)]

    @staticmethod
    def render_command(command: list[str]) -> str:
        return " ".join(command)

    def sync(
        self, python: Path, projects: list[Project], *, dry_run: bool = False
    ) -> int:
        command = self.install_command(python, projects)
        print(self.render_command(command))
        if dry_run:
            return 0
        result = subprocess.run(
            command,
            check=False,
            shell=False,
            env=self._environment(),
        )
        if result.returncode:
            return result.returncode
        return self.check(python)

    def check(self, python: Path) -> int:
        return subprocess.run(
            self.check_command(python),
            check=False,
            shell=False,
            env=self._environment(),
        ).returncode
