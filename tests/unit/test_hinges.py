"""Unit tests for table-backed frame hinge definitions."""

from __future__ import annotations

from typing import Any

import pytest

from sap2000py import SapTableSchemaError, Units
from sap2000py.model.hinges import MomentHinge

M3_TABLE_LONG = "Hinges Def 02 - Noninteracting - Deform Control - Moment M3"
M3_TABLE_WIDE = "Hinges Def 02 - Noninteracting - Deform Control - Moment M3 - v25"
ASSIGN_TABLE = "Frame Hinge Assigns 01 - General"
AUTO_FIBER_TABLE = "Frame Hinge Assigns 02 - Auto Fiber"


def _fields(keys: tuple[str, ...]) -> tuple[Any, ...]:
    return (25, len(keys), keys, keys, ("",) * len(keys), ("",) * len(keys), (True,) * len(keys), 0)


def hinge_responses(table: str, fields: tuple[str, ...]) -> dict[str, Any]:
    """Fake COM table surface for hinge tests."""

    def all_fields(table_key: str) -> tuple[Any, ...]:
        if table_key == ASSIGN_TABLE:
            return _fields(("Frame", "Hinge", "RelDist"))
        return _fields(fields)

    return {
        "GetModelIsLocked": False,
        "DatabaseTables.GetAvailableTables": (
            2,
            (table, ASSIGN_TABLE),
            ("Moment M3", "Assigns"),
            (1, 1),
            0,
        ),
        "DatabaseTables.GetAllFieldsInTable": all_fields,
        "DatabaseTables.SetTableForEditingArray": 0,
        "DatabaseTables.ApplyEditedTables": (0, 0, 0, 0, "ok", 0),
        "FrameObj.GetHingeAssigns": (2, ("H1", "H2"), (0.0, 0.75), 0),
    }


def test_define_moment_m3_maps_long_schema_and_assigns(make_model) -> None:
    h = make_model(
        hinge_responses(
            M3_TABLE_LONG,
            ("Hinge", "Point", "Plastic Rotation", "M/My", "My", "IO", "LS", "CP"),
        )
    )
    hinge = MomentHinge(
        "H1",
        100.0,
        ((0.0, 1.0), (0.02, 1.2), (0.03, 0.2), (0.04, 0.2)),
        acceptance=(0.01, 0.02, 0.03),
    )

    assert h.model.hinges.define_moment_m3(hinge) == "H1"
    h.model.hinges.assign("F1", "H1", rel_dist=0.25)
    assigns = h.model.hinges.assigned("F1")

    edit_calls = h.called("DatabaseTables.SetTableForEditingArray")
    assert edit_calls[0] == (
        M3_TABLE_LONG,
        0,
        ["Hinge", "Point", "Plastic Rotation", "M/My", "My", "IO", "LS", "CP"],
        4,
        [
            "H1",
            "B",
            0.0,
            1.0,
            100.0,
            0.01,
            0.02,
            0.03,
            "H1",
            "C",
            0.02,
            1.2,
            100.0,
            0.01,
            0.02,
            0.03,
            "H1",
            "D",
            0.03,
            0.2,
            100.0,
            0.01,
            0.02,
            0.03,
            "H1",
            "E",
            0.04,
            0.2,
            100.0,
            0.01,
            0.02,
            0.03,
        ],
    )
    assert edit_calls[1] == (ASSIGN_TABLE, 0, ["Frame", "Hinge", "RelDist"], 1, ["F1", "H1", 0.25])
    assert len(h.called("DatabaseTables.ApplyEditedTables")) == 2
    assert assigns[1].hinge == "H2"
    assert assigns[1].rel_dist == 0.75


def test_define_moment_m3_maps_wide_schema(make_model) -> None:
    h = make_model(
        hinge_responses(
            M3_TABLE_WIDE,
            (
                "Name",
                "Yield Moment",
                "B Rot",
                "B Moment Ratio",
                "C Rot",
                "C Moment Ratio",
                "D Rot",
                "D Moment Ratio",
                "E Rot",
                "E Moment Ratio",
                "Symmetric",
            ),
        )
    )
    hinge = MomentHinge(
        "Hwide",
        50.0,
        ((0.0, 1.0), (0.01, 1.1), (0.015, 0.2), (0.02, 0.2)),
    )

    h.model.hinges.define_moment_m3(hinge)

    assert h.called("DatabaseTables.SetTableForEditingArray")[0] == (
        M3_TABLE_WIDE,
        0,
        [
            "Name",
            "Yield Moment",
            "B Rot",
            "B Moment Ratio",
            "C Rot",
            "C Moment Ratio",
            "D Rot",
            "D Moment Ratio",
            "E Rot",
            "E Moment Ratio",
            "Symmetric",
        ],
        1,
        ["Hwide", 50.0, 0.0, 1.0, 0.01, 1.1, 0.015, 0.2, 0.02, 0.2, True],
    )


def test_define_moment_m3_rejects_drifted_schema_before_edit(make_model) -> None:
    h = make_model(hinge_responses(M3_TABLE_LONG, ("Hinge", "Point", "M/My", "My")))
    hinge = MomentHinge("Bad", 10.0, ((0.0, 1.0),))

    with pytest.raises(SapTableSchemaError, match="Discovered schema"):
        h.model.hinges.define_moment_m3(hinge)

    assert h.called("DatabaseTables.SetTableForEditingArray") == []
    assert h.called("DatabaseTables.ApplyEditedTables") == []


def test_define_moment_m3_requires_unlocked_model(make_model) -> None:
    responses = hinge_responses(M3_TABLE_LONG, ("Hinge", "Point", "Plastic Rotation", "M/My", "My"))
    responses["GetModelIsLocked"] = True
    h = make_model(responses)

    with pytest.raises(RuntimeError, match="unlocked"):
        h.model.hinges.define_moment_m3(MomentHinge("H1", 10.0, ((0.0, 1.0),)))

    assert h.called("DatabaseTables.GetAvailableTables") == []


def test_assign_uses_general_table_when_auto_fiber_table_is_listed_first(make_model) -> None:
    def all_fields(table_key: str) -> tuple[Any, ...]:
        if table_key == ASSIGN_TABLE:
            return _fields(("Frame", "Hinge", "RelDist"))
        return _fields(("Frame", "RelDist", "Hinge Type", "Hinge Length"))

    h = make_model(
        {
            "GetModelIsLocked": False,
            "DatabaseTables.GetAvailableTables": (
                2,
                (AUTO_FIBER_TABLE, ASSIGN_TABLE),
                ("Auto Fiber", "Assigns"),
                (1, 1),
                0,
            ),
            "DatabaseTables.GetAllFieldsInTable": all_fields,
            "DatabaseTables.SetTableForEditingArray": 0,
            "DatabaseTables.ApplyEditedTables": (0, 0, 0, 0, "ok", 0),
        }
    )

    h.model.hinges.assign("F1", "H1", rel_dist=0.25)

    assert h.called("DatabaseTables.SetTableForEditingArray")[0][0] == ASSIGN_TABLE


def test_find_table_rejects_ambiguous_prefix(make_model) -> None:
    h = make_model(
        {
            "DatabaseTables.GetAvailableTables": (
                2,
                ("Bare Prefix A", "Bare Prefix B"),
                ("A", "B"),
                (1, 1),
                0,
            ),
        }
    )

    with pytest.raises(SapTableSchemaError, match="Ambiguous"):
        h.model.hinges._find_table("Bare Prefix")


@pytest.mark.sap
def test_hinge_define_assign_round_trip_sap(client) -> None:
    """Real SAP2000 v25 schema guard; skipped unless pytest is run with --sap."""
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    p1 = m.points.add(0.0, 0.0, 0.0, name="H_P1")
    p2 = m.points.add(0.0, 0.0, 5.0, name="H_P2")
    frame = m.frames.add_by_points(p1, p2, section="Default", name="H_FRAME")
    hinge = MomentHinge(
        "S3_M3",
        1000.0,
        ((0.0, 1.0), (0.01, 1.1), (0.02, 0.2), (0.03, 0.2)),
    )

    m.hinges.define_moment_m3(hinge)
    m.hinges.assign(frame.name, hinge.name, rel_dist=0.0)

    assert any(assign.hinge == hinge.name for assign in m.hinges.assigned(frame.name))
