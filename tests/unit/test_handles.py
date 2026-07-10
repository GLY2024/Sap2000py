"""Tests for object handles."""

from __future__ import annotations

import pytest

from sap2000py import (
    AreaHandle,
    CableHandle,
    FrameHandle,
    PointHandle,
    SolidHandle,
    TendonHandle,
)
from sap2000py.handles import as_name


def test_handle_stringifies_to_name() -> None:
    assert str(PointHandle("P12")) == "P12"


def test_handles_compare_by_type_and_name() -> None:
    assert PointHandle("P1") == PointHandle("P1")
    assert PointHandle("P1") != PointHandle("P2")
    # Different handle types with the same name are not equal.
    assert PointHandle("X") != FrameHandle("X")


def test_handles_with_different_owners_compare_transitively_by_value() -> None:
    owner_a = object()
    owner_b = object()
    bound_a = PointHandle("P1", _owner=owner_a)
    unbound = PointHandle("P1")
    bound_b = PointHandle("P1", _owner=owner_b)

    assert bound_a == unbound
    assert unbound == bound_b
    assert bound_a == bound_b


def test_handles_are_hashable() -> None:
    assert len({PointHandle("P1"), PointHandle("P1"), PointHandle("P2")}) == 2
    assert hash(PointHandle("P1", _owner=object())) == hash(PointHandle("P1", _owner=object()))


def test_ownerless_live_handle_method_explains_binding_requirement() -> None:
    with pytest.raises(ValueError) as info:
        PointHandle("P1").fix()

    message = str(info.value)
    assert "not bound to a model" in message
    assert "m.points.ref('P1')" in message
    assert "m.points['P1']" in message


@pytest.mark.parametrize("handle_cls", [CableHandle, TendonHandle, AreaHandle, SolidHandle])
def test_unmanaged_handle_subclasses_keep_base_equality_and_hash(handle_cls) -> None:
    owner_a = object()
    owner_b = object()

    bound_a = handle_cls("H1", _owner=owner_a)
    bound_b = handle_cls("H1", _owner=owner_b)

    assert handle_cls("H1", _owner=owner_a) == bound_a
    assert bound_a == bound_b
    assert hash(bound_a) == hash(handle_cls("H1", _owner=owner_a))
    assert hash(bound_a) == hash(bound_b)
    assert hash(bound_a) != hash(handle_cls("H2", _owner=owner_a))
    assert hash(PointHandle("H1")) != hash(handle_cls("H1"))


def test_as_name_accepts_handle_or_str() -> None:
    assert as_name(PointHandle("P9")) == "P9"
    assert as_name("raw") == "raw"
