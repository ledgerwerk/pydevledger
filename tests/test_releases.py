from packaging.requirements import Requirement
from packaging.version import Version

from pydevledger.releases import newest_versions


def test_newest_versions_respects_all_constraints() -> None:
    requirements = [Requirement("demo>=1.0,<2"), Requirement("demo>=1.5")]
    versions = [Version("1.0"), Version("1.5"), Version("1.9"), Version("2.0")]

    compatible, latest = newest_versions(requirements, versions)

    assert compatible == Version("1.9")
    assert latest == Version("2.0")
