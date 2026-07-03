"""Tests for the typed model managers (files, points, units) over a fake COM."""

from __future__ import annotations

import pytest

from sap2000py import FrameHandle
from sap2000py.enums import DOF, ItemType, Units
from sap2000py.errors import SapNameNotFoundError
from sap2000py.model.points import PointHandle


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
    assert h.model.points.ref("P1").coordinates() == (1.5, 2.5, 3.5)


def test_points_names_empty_model(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (0, None, 0)})
    assert h.model.points.names() == []


def test_points_names_returns_list(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (2, ("P1", "P2"), 0)})
    assert h.model.points.names() == ["P1", "P2"]


def test_points_get_validates_name_before_returning_handle(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (1, ("P1",), 0)})
    assert h.model.points.get("P1").name == "P1"
    assert h.model.points["P1"].name == "P1"
    assert h.called("PointObj.GetNameList") == [(), ()]


def test_points_get_missing_name_raises_typed_error(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (1, ("P1",), 0)})
    with pytest.raises(SapNameNotFoundError, match="No point named 'P9'"):
        h.model.points.get("P9")


def test_name_not_found_error_truncates_available_names() -> None:
    names = [f"P{i}" for i in range(30)]
    error = SapNameNotFoundError("PX", kind="point", available=names)

    assert error.available == names
    assert "P24" in str(error)
    assert "P25" not in str(error)
    assert "... and 5 more" in str(error)


def test_points_ref_mints_handle_without_round_trip(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (1, ("P1",), 0)})
    p = h.model.points.ref("P9")
    assert p.name == "P9"
    assert p._owner is h.model.points
    assert h.called("PointObj.GetNameList") == []


def test_points_ref_owner_rules(make_model) -> None:
    h1 = make_model({"PointObj.GetNameList": (1, ("P2",), 0)})
    h2 = make_model()
    owned = h1.model.points.ref("P1")
    assert h1.model.points.ref(owned) is owned

    ownerless = PointHandle("P2")
    rebound = h1.model.points.ref(ownerless)
    assert rebound.name == "P2"
    assert rebound._owner is h1.model.points

    foreign = h2.model.points.ref("P3")
    with pytest.raises(ValueError, match="another manager/model"):
        h1.model.points.ref(foreign)

    with pytest.raises(TypeError, match="expected PointHandle"):
        h1.model.points.ref(FrameHandle("F1"))


def test_ownerless_handle_ref_validates_name_before_binding(make_model) -> None:
    h = make_model({"PointObj.GetNameList": (1, ("P1",), 0)})

    with pytest.raises(SapNameNotFoundError, match="No point named 'P9'"):
        h.model.points.ref(PointHandle("P9"))

    assert h.called("PointObj.GetNameList") == [()]


def test_point_handle_restrain_validates_length(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    with pytest.raises(ValueError, match="6 elements"):
        h.model.points.ref("P1").restrain([True, False])


def test_point_handle_restrain_passes_mask_and_itemtype(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    h.model.points.ref("P1").restrain(DOF.fixed())
    (args,) = h.called("PointObj.SetRestraint")
    assert args == ("P1", [True] * 6, int(ItemType.OBJECT))


def test_point_handle_restrain_is_chainable(make_model) -> None:
    h = make_model({"PointObj.AddCartesian": ("P1", 0), "PointObj.SetRestraint": 0})
    p = h.model.points.add(0, 0, 0)
    assert p.restrain(DOF.fixed()) is p
    assert h.called("PointObj.SetRestraint") == [("P1", [True] * 6, int(ItemType.OBJECT))]


def test_point_handle_restrain_accepts_dof_name_varargs(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    h.model.points.ref("P1").restrain("U1", "U3", "R2")
    (args,) = h.called("PointObj.SetRestraint")
    assert args == ("P1", [True, False, True, False, True, False], int(ItemType.OBJECT))


def test_point_handle_restrain_no_args_raises(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    with pytest.raises(ValueError, match="at least one DOF"):
        h.model.points.ref("P1").restrain()
    assert h.called("PointObj.SetRestraint") == []


def test_point_handle_restrain_explicit_none_raises(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    with pytest.raises(ValueError, match="at least one DOF"):
        h.model.points.ref("P1").restrain(None)
    assert h.called("PointObj.SetRestraint") == []


def test_point_handle_fix_pin_free(make_model) -> None:
    h = make_model({"PointObj.SetRestraint": 0})
    p = h.model.points.ref("P1")
    assert p.fix() is p
    assert p.pin() is p
    assert p.free() is p
    assert h.called("PointObj.SetRestraint") == [
        ("P1", [True] * 6, int(ItemType.OBJECT)),
        ("P1", [True, True, True, False, False, False], int(ItemType.OBJECT)),
        ("P1", [False] * 6, int(ItemType.OBJECT)),
    ]


def test_point_handle_set_spring_passes_stiffness_flags_and_itemtype(make_model) -> None:
    h = make_model({"PointObj.SetSpring": 0})
    p = h.model.points.ref("P1")

    assert p.set_spring([1, 2, 3, 4, 5, 6], local_csys=True, replace=False) is p

    assert h.called("PointObj.SetSpring") == [
        ("P1", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], int(ItemType.OBJECT), True, False)
    ]


def test_point_handle_set_spring_validates_length(make_model) -> None:
    h = make_model({"PointObj.SetSpring": 0})

    with pytest.raises(ValueError, match="6 elements"):
        h.model.points.ref("P1").set_spring([1.0, 2.0])

    assert h.called("PointObj.SetSpring") == []


def test_point_handle_constrain_passes_name_replace_and_itemtype(make_model) -> None:
    h = make_model({"PointObj.SetConstraint": 0})
    p = h.model.points.ref("P1")

    assert p.constrain("C1", replace=True) is p

    assert h.called("PointObj.SetConstraint") == [
        ("P1", "C1", int(ItemType.OBJECT), True)
    ]


def test_point_handle_reactions_delegates_to_results(
    make_model, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = make_model()
    p = h.model.points.ref("P1")
    seen: list[PointHandle] = []

    def joint_reactions(point: PointHandle) -> str:
        seen.append(point)
        return "reactions"

    monkeypatch.setattr(h.model.results, "joint_reactions", joint_reactions)

    assert p.reactions() == "reactions"
    assert seen == [p]


def test_point_handle_displacements_delegates_to_results(
    make_model, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = make_model()
    p = h.model.points.ref("P1")
    seen: list[PointHandle] = []

    def joint_displacements(point: PointHandle) -> str:
        seen.append(point)
        return "displacements"

    monkeypatch.setattr(h.model.results, "joint_displacements", joint_displacements)

    assert p.displacements() == "displacements"
    assert seen == [p]


def test_point_handle_delete_passes_name_and_itemtype(make_model) -> None:
    h = make_model({"PointObj.Delete": 0})

    h.model.points.ref("P1").delete()

    assert h.called("PointObj.Delete") == [("P1", int(ItemType.OBJECT))]


def test_ownerless_point_handle_methods_require_model_binding() -> None:
    p = PointHandle("P1")
    with pytest.raises(ValueError, match=r"m.points.ref\('P1'\)"):
        p.coordinates()


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


def test_model_version_is_cached(make_model) -> None:
    h = make_model({"GetVersion": ("25.1.0", 25.1, 0)})
    assert h.model.sap_version == "25.1.0"
    assert h.model.sap_version_major == 25
    assert h.model.sap_version == "25.1.0"
    assert h.called("GetVersion") == [("", 0.0)]
