"""Tests for SAP2000 installation discovery pure logic."""

from __future__ import annotations

from pathlib import Path

import pytest

import sap2000py.discovery as discovery_module
from sap2000py.discovery import (
    Installation,
    _discover,
    _exe_from_registry_value,
    _file_version,
    _format_version,
    _installation,
    _major,
    _version_key,
)


def test_major_parses_first_version_segment() -> None:
    assert _major("25.3.1") == 25
    assert _major("v26.0") == 26


def test_major_ignores_embedded_product_name() -> None:
    # DisplayVersion registry entries often carry a product-name prefix.
    assert _major("SAP2000 v25.3.0") == 25
    assert _major("SAP2000v25.3.0") == 25


def test_format_version_formats_and_trims_version_segments() -> None:
    assert _format_version((25 << 16) | 1, 0) == "25.1"
    assert _format_version((25 << 16) | 1, (2 << 16) | 3) == "25.1.2.3"
    assert _format_version(25 << 16, 0) == "25"
    assert _format_version(0, 0) is None


def test_installation_uses_explicit_version_without_file_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_file_version(_path: Path) -> str | None:
        raise AssertionError("_file_version should not be called")

    path = Path("C:/SAP25/SAP2000.exe")
    monkeypatch.setattr(discovery_module, "_file_version", fail_file_version)

    assert _installation(path, version="25.1.0") == Installation(
        version="25.1.0",
        major=25,
        path=path,
    )


def test_installation_missing_path_has_unknown_version(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "SAP2000.exe"

    assert _installation(path) == Installation(version=None, major=None, path=path)


def test_file_version_missing_path_returns_none(tmp_path: Path) -> None:
    assert _file_version(tmp_path / "missing.exe") is None


def test_discover_deduplicates_by_path_and_sorts_known_versions_first() -> None:
    candidates = [
        Installation(version=None, major=None, path=Path("C:/SAP/SAP2000.exe")),
        Installation(version="25.0.0", major=25, path=Path("C:/SAP25/SAP2000.exe")),
        Installation(version="25.1.0", major=25, path=Path("C:/SAP25.1/SAP2000.exe")),
        Installation(version="24.2.0", major=24, path=Path("C:/SAP24/SAP2000.exe")),
        Installation(version="25.1.0", major=25, path=Path("C:/SAP25.1/SAP2000.exe")),
    ]

    discovered = _discover(candidates)

    assert [item.version for item in discovered] == ["25.1.0", "25.0.0", "24.2.0", None]
    assert len(discovered) == 4


def test_discover_sorts_longer_patch_version_before_shared_prefix() -> None:
    candidates = [
        Installation(version="25.1", major=25, path=Path("C:/SAP251/SAP2000.exe")),
        Installation(version="25.1.1", major=25, path=Path("C:/SAP2511/SAP2000.exe")),
    ]

    discovered = _discover(candidates)

    assert [item.version for item in discovered] == ["25.1.1", "25.1"]


def test_discover_ignores_product_prefix_when_sorting_versions() -> None:
    candidates = [
        Installation(version="SAP2000 v25.1", major=25, path=Path("C:/SAP251/SAP2000.exe")),
        Installation(version="25.3", major=25, path=Path("C:/SAP253/SAP2000.exe")),
    ]

    discovered = _discover(candidates)

    assert [item.version for item in discovered] == ["25.3", "SAP2000 v25.1"]
    assert _major("SAP2000 v25.1") == 25


def test_version_key_preserves_non_prefix_2000_segment() -> None:
    assert _version_key("20.0.2000") == (20, 0, 2000)


def test_discover_prefers_known_version_for_same_executable_path() -> None:
    path = Path("C:/SAP25/SAP2000.exe")
    discovered = _discover(
        [
            Installation(version=None, major=None, path=path),
            Installation(version="25.2.0", major=25, path=path),
        ]
    )

    assert discovered == [Installation(version="25.2.0", major=25, path=path)]


def test_registry_direct_exe_value_must_exist() -> None:
    missing_exe = Path("definitely_missing/SAP2000.exe")

    assert _exe_from_registry_value(str(missing_exe)) is None
