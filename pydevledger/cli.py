from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from packaging.utils import canonicalize_name

from . import __version__
from .discovery import dependency_uses, discover
from .environment import inspect_environment, resolve_python
from .releases import fetch_pypi_versions, newest_versions
from .state import load_state, save_state


def _projects(root: Path):
    projects = discover(root)
    if not projects:
        raise RuntimeError(f"No Git-backed Python projects found below {root}")
    return projects


def cmd_scan(args: argparse.Namespace) -> int:
    projects = _projects(args.root)
    for project in sorted(projects.values(), key=lambda item: item.name.lower()):
        local = ", ".join(projects[key].name for key in sorted(project.local_dependencies))
        suffix = f"  local-deps=[{local}]" if local else ""
        print(f"{project.name:<28} {project.path}{suffix}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    projects = _projects(args.root)
    python = resolve_python(args.python)
    installed = inspect_environment(python)

    print(f"Python: {python}")
    print(f"{'PROJECT':<28} {'VERSION':<14} {'STATE':<16} SOURCE")
    for project in sorted(projects.values(), key=lambda item: item.name.lower()):
        dist = installed.get(project.key)
        if dist is None:
            print(f"{project.name:<28} {'-':<14} {'MISSING':<16} {project.path}")
            continue

        if dist.source is None:
            state = "NON-LOCAL"
        elif dist.source != project.path:
            state = "WRONG-SOURCE"
        elif dist.editable:
            state = "OK"
        else:
            state = "LOCAL-NONEDIT"
        source = str(dist.source) if dist.source else "index/unknown"
        print(f"{project.name:<28} {dist.version:<14} {state:<16} {source}")
    return 0


def cmd_dependents(args: argparse.Namespace) -> int:
    projects = _projects(args.root)
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
    projects = _projects(args.root)
    uses = dependency_uses(projects)
    python = resolve_python(args.python)
    installed = inspect_environment(python)
    seen = load_state(args.root)
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

        installed_version = installed.get(key).version if key in installed else None
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
        for use in sorted(dependency_uses_for_key, key=lambda item: item.project.name.lower()):
            print(f"    {use.project.name:<24} {use.requirement}")
        print()
        next_seen[key] = latest_text

    if args.ack:
        save_state(args.root, next_seen)
        print(f"Acknowledged observed releases in {args.root / '.pydevledger' / 'state.json'}")

    if not found:
        print("No unseen dependency releases found." if not args.all else "No dependency releases found.")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    projects = _projects(args.root)
    python = resolve_python(args.python)
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for sync but was not found on PATH")

    command = [uv, "pip", "install", "--python", str(python), "--link-mode", "copy"]
    for project in sorted(projects.values(), key=lambda item: item.name.lower()):
        command.extend(["-e", str(project.path)])

    print(" ".join(command))
    if args.dry_run:
        return 0

    result = subprocess.run(command, check=False)
    if result.returncode:
        return result.returncode

    return subprocess.run(
        [uv, "pip", "check", "--python", str(python)],
        check=False,
    ).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pydevledger")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="workspace root")
    parser.add_argument("--python", type=Path, help="Python interpreter / venv to inspect")

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="discover Git-backed pyproject projects")
    scan.set_defaults(func=cmd_scan)

    status = sub.add_parser("status", help="compare local projects with the environment")
    status.set_defaults(func=cmd_status)

    dependents = sub.add_parser("dependents", help="show local consumers of a dependency")
    dependents.add_argument("package")
    dependents.set_defaults(func=cmd_dependents)

    updates = sub.add_parser("updates", help="check direct dependencies for PyPI releases")
    updates.add_argument("--all", action="store_true", help="show seen releases too")
    updates.add_argument("--ack", action="store_true", help="record displayed latest releases as seen")
    updates.add_argument("--include-prerelease", action="store_true")
    updates.set_defaults(func=cmd_updates)

    sync = sub.add_parser("sync", help="install all discovered projects editable with uv")
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
        return int(args.func(args))
    except RuntimeError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
