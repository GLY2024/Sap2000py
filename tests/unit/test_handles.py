"""Tests for object handles."""

from __future__ import annotations

from sap2000py import FrameHandle, PointHandle
from sap2000py.handles import as_name


def test_handle_stringifies_to_name() -> None:
    assert str(PointHandle("P12")) == "P12"


def test_handles_compare_by_type_and_name() -> None:
    assert PointHandle("P1") == PointHandle("P1")
    assert PointHandle("P1") != PointHandle("P2")
    # Different handle types with the same name are not equal.
    assert PointHandle("X") != FrameHandle("X")


def test_owner_excluded_from_equality() -> None:
    assert PointHandle("P1", _owner=object()) == PointHandle("P1", _owner=object())


def test_handles_are_hashable() -> None:
    assert len({PointHandle("P1"), PointHandle("P1"), PointHandle("P2")}) == 2


def test_as_name_accepts_handle_or_str() -> None:
    assert as_name(PointHandle("P9")) == "P9"
    assert as_name("raw") == "raw"
