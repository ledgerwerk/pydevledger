from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from packaging.utils import canonicalize_name

from . import __version__
from .config import SyncConfig, WorkspaceConfig, is_excluded_relative_path, load_config
from .discovery import dependency_uses, discover
from .environment import classify_project_install, inspect_environment, resolve_python
from .package_manager import get_package_manager
from .releases import fetch_pypi_versions, newest_versions
from .state import load_state, save_state
from .types import Project


@dataclass(frozen=True, slots=True)
class AppContext:
    root: Path
    config: WorkspaceConfig


def _projects(context: AppContext) -> dict[str, Project]:
    projects = discover(context.root, config=context.config.discovery)
    if not projects:
        raise RuntimeError(f"No Git-backed Python projects found below {context.root}")
    return projects


def cmd_scan(args: argparse.Namespace) -> int:
    projects = _projects(args.context)
    for project in sorted(projects.values(), key=lambda item: item.name.lower()):
        local = ", ".join(
            projects[key].name for key in sorted(project.local_dependencies)
        )
        suffix = f"  local-deps=[{local}]" if local else ""
        print(f"{project.name:<28} {project.path}{suffix}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    context = args.context
    projects = _projects(context)
    python = resolve_python(args.python, root=context.root)
    installed = inspect_environment(python)

    print(f"Python: {python}")
    print(f"{'PROJECT':<28} {'VERSION':<14} {'STATE':<16} SOURCE")
    for project in sorted(projects.values(), key=lambda item: item.name.lower()):
        dist = installed.get(project.key)
        state = classify_project_install(project, dist)
        if dist is None:
            print(f"{project.name:<28} {'-':<14} {state:<16} {project.path}")
            continue
        source = str(dist.source) if dist.source else "index/unknown"
        print(f"{project.name:<28} {dist.version:<14} {state:<16} {source}")
    return 0


def cmd_dependents(args: argparse.Namespace) -> int:
    projects = _projects(args.context)
    uses = dependency_uses(projects)
    key = canonicalize_name(args.package)
    matches = uses.get(key, [])
    if not matches:
        print(f"No local project declares a direct dependency on {args.package}.")
        return 1

    print(args.package)
    for use in sorted(matches, key=lambda item: item.project.name.lower()):
        print(f"  {use.project.name:<28} {use.requirement}")
    return 0


def cmd_updates(args: argparse.Namespace) -> int:
    context = args.context
    projects = _projects(context)
    uses = dependency_uses(projects)
    python = resolve_python(args.python, root=context.root)
    installed = inspect_environment(python)
    seen = load_state(context.root)
    next_seen = dict(seen)

    found = False
    for key in sorted(uses):
        dependency_uses_for_key = uses[key]
        requirements = [item.requirement for item in dependency_uses_for_key]
        try:
            versions = fetch_pypi_versions(
                requirements[0].name,
                include_prerelease=args.include_prerelease,
            )
        except RuntimeError as exc:
            print(f"{requirements[0].name}: ERROR {exc}", file=sys.stderr)
            continue

        compatible, latest = newest_versions(requirements, versions)
        if latest is None:
            continue

        distribution = installed.get(key)
        installed_version = distribution.version if distribution is not None else None
        latest_text = str(latest)
        is_new = seen.get(key) != latest_text
        has_upgrade = installed_version is None or installed_version != latest_text

        if not is_new and not args.all:
            continue

        found = True
        marker = "NEW" if is_new else "SEEN"
        print(f"{requirements[0].name}  [{marker}]")
        print(f"  installed:         {installed_version or '-'}")
        print(f"  latest compatible: {compatible or '-'}")
        print(f"  latest upstream:   {latest}")
        if not has_upgrade:
            print("  environment:       already at latest upstream")
        print("  used by:")
        for use in sorted(
            dependency_uses_for_key, key=lambda item: item.project.name.lower()
        ):
            print(f"    {use.project.name:<24} {use.requirement}")
        print()
        next_seen[key] = latest_text

    if args.ack:
        save_state(context.root, next_seen)
        print(
            f"Acknowledged observed releases in {context.root / '.pydevledger' / 'state.json'}"
        )
    if not found:
        print(
            "No unseen dependency releases found."
            if not args.all
            else "No dependency releases found."
        )
    return 0


def select_sync_projects(
    root: Path,
    projects: dict[str, Project],
    config: SyncConfig,
) -> tuple[list[Project], list[Project]]:
    root = root.resolve()
    selected: list[Project] = []
    skipped: list[Project] = []
    for project in sorted(projects.values(), key=lambda item: item.name.lower()):
        relative = PurePosixPath(project.path.resolve().relative_to(root).as_posix())
        target = (
            skipped
            if is_excluded_relative_path(relative, config.exclude_paths)
            else selected
        )
        target.append(project)
    return selected, skipped


def _warn_sync_dependency_edges(
    selected: list[Project], skipped: list[Project]
) -> None:
    skipped_by_key = {project.key: project for project in skipped}
    for project in selected:
        for dependency_key in project.local_dependencies:
            skipped_project = skipped_by_key.get(dependency_key)
            if skipped_project is None:
                continue
            requirement = next(
                (
                    item
                    for item in project.dependencies
                    if canonicalize_name(item.name) == dependency_key
                ),
                None,
            )
            dependency_name = str(requirement or skipped_project.name)
            print(
                f"WARNING: {project.name} declares {dependency_name}, but local project "
                f"{skipped_project.name} is excluded from sync."
            )
            print("         uv may still resolve the package as a dependency.")


def cmd_sync(args: argparse.Namespace) -> int:
    context = args.context
    projects = _projects(context)
    selected, skipped = select_sync_projects(
        context.root, projects, context.config.sync
    )
    if skipped:
        print("Skipping sync-excluded projects:")
        for project in skipped:
            print(f"  {project.name:<28} {project.path}")
        _warn_sync_dependency_edges(selected, skipped)
    if not selected:
        print("No projects selected for sync.")
        return 0
    python = resolve_python(args.python, root=context.root)
    manager = get_package_manager(context.config.package_manager)
    return manager.sync(python, selected, dry_run=args.dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pydevledger")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="workspace root")
    parser.add_argument(
        "--python", type=Path, help="Python interpreter / venv to inspect"
    )
    parser.add_argument("--config", type=Path, help="workspace configuration file")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH",
        help="temporarily exclude a root-relative directory subtree",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="discover Git-backed pyproject projects")
    scan.set_defaults(func=cmd_scan)

    status = sub.add_parser(
        "status", help="compare local projects with the environment"
    )
    status.set_defaults(func=cmd_status)

    dependents = sub.add_parser(
        "dependents", help="show local consumers of a dependency"
    )
    dependents.add_argument("package")
    dependents.set_defaults(func=cmd_dependents)

    updates = sub.add_parser(
        "updates", help="check direct dependencies for PyPI releases"
    )
    updates.add_argument("--all", action="store_true", help="show seen releases too")
    updates.add_argument(
        "--ack", action="store_true", help="record displayed latest releases as seen"
    )
    updates.add_argument("--include-prerelease", action="store_true")
    updates.set_defaults(func=cmd_updates)

    sync = sub.add_parser(
        "sync",
        help="install all discovered projects editable with the configured backend",
    )
    sync.add_argument("--dry-run", action="store_true")
    sync.set_defaults(func=cmd_sync)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.root = args.root.expanduser().resolve()
    if not args.root.is_dir():
        parser.error(f"root is not a directory: {args.root}")

    try:
        args.context = AppContext(
            root=args.root,
            config=load_config(args.root, args.config, cli_exclude_paths=args.exclude),
        )
        return int(args.func(args))
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
