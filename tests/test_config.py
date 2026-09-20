from pathlib import Path

import pytest

from pydevledger.config import (
    CONFIG_FILE,
    DEFAULT_EXCLUDED_NAMES,
    load_config,
)


def write_config(root: Path, text: str) -> Path:
    path = root / CONFIG_FILE
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.package_manager.system == "uv"
    assert config.package_manager.uv.link_mode == "copy"
    assert config.discovery.exclude_names == DEFAULT_EXCLUDED_NAMES
    assert config.discovery.exclude_paths == ()
    assert config.discovery.include_hidden is False
    assert config.path is None


def test_valid_full_config_and_cli_exclusions(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """schema_version = 1

[package_manager]
system = "uv"

[package_manager.uv]
link_mode = "hardlink"

[discovery]
exclude_names = ["generated", "generated"]
exclude_paths = ["archive/./old", "archive"]
include_hidden = true
""",
    )
    config = load_config(tmp_path, cli_exclude_paths=["scratch", "archive"])
    assert config.path == path.resolve()
    assert config.package_manager.uv.link_mode == "hardlink"
    assert "generated" in config.discovery.exclude_names
    assert ".git" in config.discovery.exclude_names
    assert config.discovery.exclude_paths == ("archive/old", "archive", "scratch")
    assert config.discovery.include_hidden is True


@pytest.mark.parametrize("link_mode", ["clone", "copy", "hardlink", "symlink"])
def test_valid_uv_link_modes(tmp_path: Path, link_mode: str) -> None:
    write_config(
        tmp_path,
        f'schema_version = 1\n[package_manager.uv]\nlink_mode = "{link_mode}"\n',
    )
    assert load_config(tmp_path).package_manager.uv.link_mode == link_mode


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("schema_version = 3", "Unsupported pydevledger config schema_version"),
        ('schema_version = 1\n[package_manager]\nsystem = "poetry"', "poetry"),
        ('schema_version = 1\n[package_manager.uv]\nlink_mode = "bad"', "uv.link_mode"),
        ("schema_version = 1\n[package_manager.uv]\nother = true", "Unknown key"),
        ('schema_version = 1\n[discovery]\nexlude_paths = ["x"]', "Unknown key"),
        ("schema_version = 1\nother = true", "Unknown key"),
        ("schema_version = 1\n[discovery]\nexclude_names = [1]", "exclude_names"),
        ('schema_version = 1\n[discovery]\ninclude_hidden = "yes"', "include_hidden"),
    ],
)
def test_invalid_config_is_actionable(tmp_path: Path, text: str, message: str) -> None:
    write_config(tmp_path, text)
    with pytest.raises(RuntimeError, match=message):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "excluded", ["", "/absolute/path", "../outside", "a/../../outside", "."]
)
def test_invalid_exclude_path(tmp_path: Path, excluded: str) -> None:
    write_config(
        tmp_path, f'schema_version = 1\n[discovery]\nexclude_paths = ["{excluded}"]\n'
    )
    with pytest.raises(RuntimeError, match="exclude_paths"):
        load_config(tmp_path)


def test_missing_schema_version_is_rejected(tmp_path: Path) -> None:
    write_config(tmp_path, "[discovery]\ninclude_hidden = true\n")
    with pytest.raises(RuntimeError, match="schema_version"):
        load_config(tmp_path)


def test_explicit_missing_config_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        load_config(tmp_path, tmp_path / "missing.toml")


def test_schema_v1_defaults_sync_exclusions(tmp_path: Path) -> None:
    write_config(tmp_path, "schema_version = 1\n")
    assert load_config(tmp_path).sync.exclude_paths == ()


def test_schema_v2_parses_and_normalizes_sync_exclusions(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        """schema_version = 2

[sync]
exclude_paths = ["g2lex-data", "experimental/./desktop-only", "g2lex-data"]
""",
    )
    assert load_config(tmp_path).sync.exclude_paths == (
        "g2lex-data",
        "experimental/desktop-only",
    )


@pytest.mark.parametrize(
    "excluded", ["", ".", "../outside", "a/../../outside", "/absolute/path"]
)
def test_invalid_sync_exclude_path(tmp_path: Path, excluded: str) -> None:
    write_config(
        tmp_path,
        f"schema_version = 2\n[sync]\nexclude_paths = [{excluded!r}]\n",
    )
    with pytest.raises(RuntimeError, match="sync.exclude_paths"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "text",
    [
        "schema_version = 2\n[sync]\nexclude_paths = 'g2lex-data'\n",
        "schema_version = 2\n[sync]\nexclude_paths = ['g2lex-data', 1]\n",
    ],
)
def test_sync_exclude_paths_must_be_string_array(tmp_path: Path, text: str) -> None:
    write_config(tmp_path, text)
    with pytest.raises(RuntimeError, match="sync.exclude_paths"):
        load_config(tmp_path)


def test_unknown_sync_key_is_actionable(tmp_path: Path) -> None:
    write_config(tmp_path, "schema_version = 2\n[sync]\nexlude_paths = ['x']\n")
    with pytest.raises(RuntimeError, match="Unknown key.*exlude_paths"):
        load_config(tmp_path)
