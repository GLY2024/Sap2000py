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


def test_bound_handles_with_different_owners_are_not_equal() -> None:
    owner_a = object()
    owner_b = object()

    assert PointHandle("P1", _owner=owner_a) == PointHandle("P1", _owner=owner_a)
    assert PointHandle("P1", _owner=owner_a) != PointHandle("P1", _owner=owner_b)
    assert PointHandle("P1") == PointHandle("P1", _owner=owner_a)


def test_handles_are_hashable() -> None:
    assert len({PointHandle("P1"), PointHandle("P1"), PointHandle("P2")}) == 2
    assert hash(PointHandle("P1", _owner=object())) == hash(PointHandle("P1", _owner=object()))


def test_as_name_accepts_handle_or_str() -> None:
    assert as_name(PointHandle("P9")) == "P9"
    assert as_name("raw") == "raw"
