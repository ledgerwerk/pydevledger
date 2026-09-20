from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version


def fetch_pypi_versions(name: str, *, include_prerelease: bool = False) -> list[Version]:
    url = f"https://pypi.org/pypi/{quote(name)}/json"
    request = Request(url, headers={"User-Agent": "pydevledger/0 (MVP)"})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed PyPI host
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot query PyPI for {name}: {exc}") from exc

    versions: list[Version] = []
    for raw, files in payload.get("releases", {}).items():
        if files and all(bool(item.get("yanked")) for item in files):
            continue
        try:
            version = Version(raw)
        except InvalidVersion:
            continue
        if not include_prerelease and version.is_prerelease:
            continue
        versions.append(version)

    return sorted(set(versions))


def newest_versions(
    requirements: list[Requirement],
    versions: list[Version],
) -> tuple[Version | None, Version | None]:
    latest = versions[-1] if versions else None
    if not versions:
        return None, None

    compatible = [
        version
        for version in versions
        if all(req.specifier.contains(version, prereleases=True) for req in requirements)
    ]
    return (compatible[-1] if compatible else None), latest
