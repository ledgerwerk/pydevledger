import pytest

from pydevledger.config import PackageManagerConfig, UvConfig
from pydevledger.package_manager import get_package_manager
from pydevledger.uv import UvPackageManager


def test_default_and_configured_uv_select_uv_backend() -> None:
    assert isinstance(get_package_manager(PackageManagerConfig()), UvPackageManager)
    assert isinstance(
        get_package_manager(PackageManagerConfig(uv=UvConfig(link_mode="symlink"))),
        UvPackageManager,
    )


def test_unsupported_backend_has_no_fallback() -> None:
    with pytest.raises(
        RuntimeError, match="Unsupported package manager 'pip'; supported: uv"
    ):
        get_package_manager(PackageManagerConfig(system="pip"))


def test_uv_backend_retains_configured_link_mode() -> None:
    manager = get_package_manager(
        PackageManagerConfig(
            uv=UvConfig(
                link_mode="hardlink",
                environment=(("MATHLIB", "m"),),
            )
        )
    )
    assert isinstance(manager, UvPackageManager)
    assert manager.config.link_mode == "hardlink"
    assert manager.config.environment == (("MATHLIB", "m"),)
