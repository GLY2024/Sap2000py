"""Tests for enums and DOF helpers."""

from __future__ import annotations

import pytest

from sap2000py.enums import (
    DOF,
    DofSpec,
    ItemType,
    ItemTypeElm,
    LoadPatternType,
    MatType,
    Units,
    dof_mask,
    to_dof_mask,
)


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


def test_dof_mask_rejects_empty_name_sequence() -> None:
    with pytest.raises(ValueError, match="DOF name sequence cannot be empty"):
        dof_mask([])


def test_to_dof_mask_accepts_name_sequence_bool_mask_and_none() -> None:
    assert to_dof_mask("R2") == [False, False, False, False, True, False]
    assert to_dof_mask(["U1", "R3"]) == [True, False, False, False, False, True]
    assert to_dof_mask([True, False, False, False, False, True]) == [
        True,
        False,
        False,
        False,
        False,
        True,
    ]
    assert to_dof_mask(None, default=True) == [True] * 6
    assert to_dof_mask(None, default=False) == [False] * 6


def test_to_dof_mask_rejects_short_bool_mask() -> None:
    with pytest.raises(ValueError, match="6 elements"):
        to_dof_mask([True])


def test_to_dof_mask_rejects_empty_sequence_even_with_default() -> None:
    with pytest.raises(ValueError, match="DOF name sequence cannot be empty"):
        to_dof_mask([], default=True)


def test_dof_spec_alias_accepts_supported_forms() -> None:
    specs: list[DofSpec] = ["U1", ["U1"], [True, False, False, False, False, False], None]
    assert len(specs) == 4


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


def test_item_type_elm_values() -> None:
    assert int(ItemTypeElm.OBJECT_ELM) == 0
    assert int(ItemTypeElm.ELEMENT_ELM) == 1
    assert int(ItemTypeElm.GROUP_ELM) == 2
    assert int(ItemTypeElm.SELECTION_ELM) == 3


def test_mat_type_values() -> None:
    assert int(MatType.STEEL) == 1
    assert int(MatType.CONCRETE) == 2
    assert int(MatType.TENDON) == 7
    assert int(MatType.MASONRY) == 8


def test_load_pattern_type_values() -> None:
    assert int(LoadPatternType.DEAD) == 1
    assert int(LoadPatternType.WIND) == 6
    assert int(LoadPatternType.PRESTRESS) == 12
