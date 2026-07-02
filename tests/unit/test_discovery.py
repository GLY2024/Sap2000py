"""Tests for SAP2000 installation discovery pure logic."""

from __future__ import annotations

from pathlib import Path

from sap2000py.discovery import Installation, _discover, _exe_from_registry_value, _major


def test_major_parses_first_version_segment() -> None:
    assert _major("25.3.1") == 25
    assert _major("v26.0") == 26


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
