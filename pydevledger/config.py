from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast

CONFIG_FILE = ".pydevledger.toml"
CONFIG_VERSION = 1

DEFAULT_EXCLUDED_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "solution",
        "starting_code",
    }
)
UV_LINK_MODES = frozenset({"clone", "copy", "hardlink", "symlink"})
UvLinkMode = Literal["clone", "copy", "hardlink", "symlink"]


@dataclass(frozen=True, slots=True)
class UvConfig:
    link_mode: UvLinkMode = "copy"


@dataclass(frozen=True, slots=True)
class PackageManagerConfig:
    system: str = "uv"
    uv: UvConfig = UvConfig()


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    exclude_names: frozenset[str] = DEFAULT_EXCLUDED_NAMES
    exclude_paths: tuple[str, ...] = ()
    include_hidden: bool = False


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    package_manager: PackageManagerConfig = PackageManagerConfig()
    discovery: DiscoveryConfig = DiscoveryConfig()
    path: Path | None = None


def default_config() -> WorkspaceConfig:
    return WorkspaceConfig()


def _error(path: Path, message: str) -> RuntimeError:
    return RuntimeError(f"{message} in {path}")


def _require_table(value: object, name: str, path: Path) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _error(path, f"{name} must be a table")
    return value


def _reject_unknown(table: dict[str, object], allowed: set[str], prefix: str, path: Path) -> None:
    for key in table:
        if key not in allowed:
            supported = ", ".join(sorted(allowed))
            raise _error(path, f"Unknown key {prefix}.{key}; supported: {supported}")


def _parse_exclude_names(value: object, path: Path) -> frozenset[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _error(path, "discovery.exclude_names must be an array of strings")
    names: set[str] = set()
    for index, name in enumerate(value):
        if not name or "/" in name or "\\" in name:
            raise _error(path, f"discovery.exclude_names[{index}] must be a non-empty directory basename")
        names.add(name)
    return frozenset(names)


def normalize_exclude_path(value: str, *, field: str = "exclude_paths") -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must contain non-empty relative paths")
    if "\\" in value:
        raise ValueError(f"{field} must use '/' as the path separator: {value!r}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or candidate == PurePosixPath("."):
        raise ValueError(f"{field} must be a relative path without '..': {value!r}")
    normalized = "/".join(part for part in candidate.parts if part not in ("", "."))
    if not normalized:
        raise ValueError(f"{field} must contain non-empty relative paths")
    return normalized


def _parse_exclude_paths(value: object, path: Path, *, field: str = "discovery.exclude_paths") -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _error(path, f"{field} must be an array of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        try:
            normalized.append(normalize_exclude_path(item, field=f"{field}[{index}]"))
        except ValueError as exc:
            raise _error(path, str(exc)) from exc
    return tuple(dict.fromkeys(normalized))


def _parse_config(path: Path, data: dict[str, object]) -> WorkspaceConfig:
    _reject_unknown(data, {"schema_version", "package_manager", "discovery"}, "top-level", path)
    if "schema_version" not in data:
        raise _error(path, "Missing schema_version; expected 1")
    version = data["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise _error(path, "schema_version must be an integer")
    if version != CONFIG_VERSION:
        raise _error(path, f"Unsupported pydevledger config schema_version {version}; expected {CONFIG_VERSION}")

    package_manager = PackageManagerConfig()
    raw_package_manager = data.get("package_manager")
    if raw_package_manager is not None:
        package_table = _require_table(raw_package_manager, "package_manager", path)
        _reject_unknown(package_table, {"system", "uv"}, "[package_manager]", path)
        system = package_table.get("system", "uv")
        if not isinstance(system, str) or not system:
            raise _error(path, "package_manager.system must be a non-empty string")
        if system != "uv":
            raise _error(path, f"Unsupported package manager {system!r}; supported: uv")
        raw_uv = package_table.get("uv", {})
        uv_table = _require_table(raw_uv, "package_manager.uv", path)
        _reject_unknown(uv_table, {"link_mode"}, "[package_manager.uv]", path)
        link_mode = uv_table.get("link_mode", "copy")
        if not isinstance(link_mode, str) or link_mode not in UV_LINK_MODES:
            choices = ", ".join(sorted(UV_LINK_MODES))
            raise _error(path, f"uv.link_mode must be one of {choices}")
        package_manager = PackageManagerConfig(
            system=system,
            uv=UvConfig(link_mode=cast(UvLinkMode, link_mode)),
        )

    discovery = DiscoveryConfig()
    raw_discovery = data.get("discovery")
    if raw_discovery is not None:
        discovery_table = _require_table(raw_discovery, "discovery", path)
        _reject_unknown(discovery_table, {"exclude_names", "exclude_paths", "include_hidden"}, "[discovery]", path)
        names = frozenset()
        if "exclude_names" in discovery_table:
            names = _parse_exclude_names(discovery_table["exclude_names"], path)
        paths = ()
        if "exclude_paths" in discovery_table:
            paths = _parse_exclude_paths(discovery_table["exclude_paths"], path)
        include_hidden = discovery_table.get("include_hidden", False)
        if not isinstance(include_hidden, bool):
            raise _error(path, "discovery.include_hidden must be a boolean")
        discovery = DiscoveryConfig(
            exclude_names=DEFAULT_EXCLUDED_NAMES | names,
            exclude_paths=paths,
            include_hidden=include_hidden,
        )

    return WorkspaceConfig(package_manager=package_manager, discovery=discovery, path=path)


def load_config(
    root: Path,
    explicit: Path | None = None,
    *,
    cli_exclude_paths: list[str] | None = None,
) -> WorkspaceConfig:
    root = root.expanduser().resolve()
    path = explicit.expanduser().resolve() if explicit is not None else root / CONFIG_FILE
    if explicit is None and not path.exists():
        config = default_config()
    else:
        if not path.is_file():
            raise RuntimeError(f"Cannot read {path}: file does not exist")
        try:
            with path.open("rb") as stream:
                data = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise RuntimeError(f"Cannot read {path}: {exc}") from exc
        config = _parse_config(path, data)

    if cli_exclude_paths:
        additions: list[str] = []
        for index, item in enumerate(cli_exclude_paths):
            try:
                additions.append(normalize_exclude_path(item, field=f"--exclude[{index}]"))
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc
        discovery = config.discovery
        config = WorkspaceConfig(
            package_manager=config.package_manager,
            discovery=DiscoveryConfig(
                exclude_names=discovery.exclude_names,
                exclude_paths=tuple(dict.fromkeys((*discovery.exclude_paths, *additions))),
                include_hidden=discovery.include_hidden,
            ),
            path=config.path,
        )
    return config
