"""Tests for the typed model managers (files, points, units) over a fake COM."""

from __future__ import annotations

import pytest

from sap2000py.enums import DOF, ItemType, Units
from sap2000py.handles import PointHandle


def test_new_blank_sets_units_then_creates(make_model) -> None:
    h = make_model({"InitializeNewModel": 0, "File.NewBlank": 0})
    h.model.files.new_blank(units=Units.KN_M_C)
    assert h.called("InitializeNewModel") == [(int(Units.KN_M_C),)]
    assert h.called("File.NewBlank") == [()]


def test_save_as_passes_path(make_model) -> None:
    h = make_model({"File.Save": 0})
    h.model.files.save("C:/tmp/model.sdb")
    assert h.called("File.Save") == [("C:/tmp/model.sdb",)]


def test_save_current_passes_empty(make_model) -> None:
    h = make_model({"File.Save": 0})
    h.model.files.save()
    assert h.called("File.Save") == [("",)]


def test_points_add_returns_handle_with_assigned_name(make_model) -> None:
    h = make_model({"PointObj.AddCartesian": ("P1", 0)})
    p = h.model.points.add(1.0, 2.0, 3.0, name="P1")
    assert isinstance(p, PointHandle)
    assert p.name == "P1"
    # MergeOff is the inverse of merge=True default.
    (args,) = h.called("PointObj.AddCartesian")
    assert args == (1.0, 2.0, 3.0, "", "P1", "Global", False, 0)


def test_points_add_merge_off(make_model) -> None:
    h = make_model({"PointObj.AddCartesian": ("P2", 0)})
    h.model.points.add(0, 0, 0, merge=False)
    (args,) = h.called("PointObj.AddCartesian")
    assert args[6] is True  # MergeOff


def test_points_count_uses_value_path(make_model) -> None:
    h = make_model({"PointObj.Count": 7})
    assert h.model.points.count() == 7


def test_points_coordinates_unpacks_three_floats(make_model) -> None:
    h = make_model({"PointObj.GetCoordCartesian": (1.5, 2.5, 3.5, 0)})
    assert h.model.points.coordinates("P1") == (1.5, 2.5, 3.5)


def test_points_names_empty_model(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (0, None, 0)})
    assert h.model.points.names() == []


def test_points_names_returns_list(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (2, ("P1", "P2"), 0)})
    assert h.model.points.names() == ["P1", "P2"]


def test_set_restraints_validates_length(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    with pytest.raises(ValueError, match="6 elements"):
        h.model.points.set_restraints("P1", [True, False])


def test_set_restraints_passes_mask_and_itemtype(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    h.model.points.set_restraints("P1", DOF.fixed())
    (args,) = h.called("PointObj.SetRestraint")
    assert args == ("P1", [True] * 6, int(ItemType.OBJECT))


def test_units_context_manager_restores_previous(make_model) -> None:
    # GetPresentUnits is queried before switching and again to restore.
    units_seq = iter([Units.N_M_C, Units.KN_MM_C])
    h = make_model(
        {
            "GetPresentUnits": lambda: int(next(units_seq)),
            "SetPresentUnits": 0,
        }
    )
    with h.model.units(Units.KN_MM_C):
        pass
    sets = h.called("SetPresentUnits")
    # First switches to KN_MM_C, then restores to the original N_M_C.
    assert sets == [(int(Units.KN_MM_C),), (int(Units.N_M_C),)]
