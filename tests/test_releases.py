from packaging.requirements import Requirement
from packaging.version import Version

from pydevledger.releases import newest_versions


def test_newest_versions_respects_all_constraints() -> None:
    requirements = [Requirement("demo>=1.0,<2"), Requirement("demo>=1.5")]
    versions = [Version("1.0"), Version("1.5"), Version("1.9"), Version("2.0")]

    compatible, latest = newest_versions(requirements, versions)

    assert compatible == Version("1.9")
    assert latest == Version("2.0")


def test_newest_versions_with_empty_versions() -> None:
    assert newest_versions([Requirement("demo>=1")], []) == (None, None)


def test_newest_versions_with_only_incompatible_versions() -> None:
    compatible, latest = newest_versions(
        [Requirement("demo<1")],
        [Version("1.0"), Version("2.0")],
    )
    assert compatible is None
    assert latest == Version("2.0")


def test_newest_versions_intersects_multiple_consumers() -> None:
    compatible, latest = newest_versions(
        [Requirement("demo>=1,<3"), Requirement("demo>=2,<2.5")],
        [Version("1.9"), Version("2.0"), Version("2.4"), Version("2.5")],
    )
    assert compatible == Version("2.4")
    assert latest == Version("2.5")
