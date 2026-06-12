"""Tests for enums and DOF helpers."""

from __future__ import annotations

import pytest

from sap2000py.enums import DOF, ItemType, Units, dof_mask


def test_units_values_match_oapi_ids() -> None:
    assert int(Units.KN_M_C) == 6
    assert int(Units.LB_IN_F) == 1
    assert int(Units.TON_CM_C) == 16


def test_dof_mask_basic() -> None:
    assert dof_mask(["U1", "R3"]) == [True, False, False, False, False, True]


def test_dof_mask_is_case_insensitive() -> None:
    assert dof_mask(["u2"]) == [False, True, False, False, False, False]


def test_dof_mask_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="not a valid DOF"):
        dof_mask(["U7"])


def test_dof_constructors() -> None:
    assert DOF.fixed() == [True] * 6
    assert DOF.free() == [False] * 6
    assert DOF.pinned() == [True, True, True, False, False, False]
    assert DOF.of("U1", "U3") == [True, False, True, False, False, False]


def test_dof_returns_fresh_lists() -> None:
    a = DOF.fixed()
    a[0] = False
    assert DOF.fixed()[0] is True  # not mutated by previous call


def test_item_type_values() -> None:
    assert int(ItemType.OBJECT) == 0
    assert int(ItemType.GROUP) == 1
    assert int(ItemType.SELECTED) == 2
