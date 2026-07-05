"""Unit tests for the M2 typed managers over a fake COM tree."""

from __future__ import annotations

import pytest

from sap2000py import (
    FrameHandle,
    FrameSectionHandle,
    LinkHandle,
    LinkPropHandle,
    MaterialHandle,
    PointHandle,
)
from sap2000py.enums import ItemType, ItemTypeElm, LoadPatternType, MatType
from sap2000py.errors import SapAnalysisError, SapApiError, SapError, SapNameNotFoundError
from sap2000py.model.results import ResultTable

# -- materials --------------------------------------------------------------


def test_materials_add_returns_handle_and_passes_args(make_model) -> None:
    h = make_model({"PropMaterial.AddMaterial": ["AUTO-S355", 0], "PropMaterial.ChangeName": 0})

    mat = h.model.materials.add(
        "S355",
        MatType.STEEL,
        grade="EN 1993-1-1 S355",
        region="Europe",
        standard="EN",
    )

    assert isinstance(mat, MaterialHandle)
    assert mat.name == "S355"
    assert mat._owner is h.model.materials
    assert h.called("PropMaterial.AddMaterial") == [
        ("", int(MatType.STEEL), "Europe", "EN", "EN 1993-1-1 S355")
    ]
    assert h.called("PropMaterial.ChangeName") == [("AUTO-S355", "S355")]


def test_add_concrete_builds_grade_string_and_renames(make_model) -> None:
    h = make_model({"PropMaterial.AddMaterial": ["JTG-C40", 0], "PropMaterial.ChangeName": 0})
    mat = h.model.materials.add_concrete("C40", grade="C40", code="JTG")
    assert isinstance(mat, MaterialHandle)
    assert mat.name == "C40"
    (add_args,) = h.called("PropMaterial.AddMaterial")
    assert add_args == ("", int(MatType.CONCRETE), "China", "JTG", "JTG D62-2004 C40")
    assert h.called("PropMaterial.ChangeName") == [("JTG-C40", "C40")]


def test_add_concrete_tb_uses_legacy_sap_grade_string(make_model) -> None:
    h = make_model({"PropMaterial.AddMaterial": ["TB-C30", 0], "PropMaterial.ChangeName": 0})
    h.model.materials.add_concrete("C30", grade="C30", code="TB")
    (add_args,) = h.called("PropMaterial.AddMaterial")
    assert add_args == ("", int(MatType.CONCRETE), "China", "TB", "TB10002.3 C30")


def test_add_steel_gb_grade_string(make_model) -> None:
    h = make_model({"PropMaterial.AddMaterial": ["GB-Q345", 0], "PropMaterial.ChangeName": 0})
    h.model.materials.add_steel("Q345", grade="Q345", code="GB")
    (add_args,) = h.called("PropMaterial.AddMaterial")
    assert add_args == ("", int(MatType.STEEL), "China", "GB", "Q345")


def test_add_isotropic_sets_properties(make_model) -> None:
    h = make_model(
        {
            "PropMaterial.SetMaterial": 0,
            "PropMaterial.SetMPIsotropic": 0,
            "PropMaterial.SetWeightAndMass": 0,
        }
    )
    h.model.materials.add_isotropic("S", modulus=2.1e8, poisson=0.3, weight_per_volume=78.5)
    assert h.called("PropMaterial.SetMPIsotropic") == [("S", 2.1e8, 0.3, 0.0)]
    assert h.called("PropMaterial.SetWeightAndMass") == [("S", 1, 78.5)]


def test_material_handle_set_weight_per_volume_passes_value_and_is_chainable(
    make_model,
) -> None:
    h = make_model({"PropMaterial.SetWeightAndMass": 0})
    mat = h.model.materials.ref("C40")

    assert mat.set_weight_per_volume(25) is mat

    assert h.called("PropMaterial.SetWeightAndMass") == [("C40", 1, 25.0)]


def test_material_handle_delete_passes_name(make_model) -> None:
    h = make_model({"PropMaterial.Delete": 0})

    h.model.materials.ref("C40").delete()

    assert h.called("PropMaterial.Delete") == [("C40",)]


def test_materials_names_empty_model(make_model) -> None:
    h = make_model({"PropMaterial.GetNameList": (0, None, 0)})

    assert h.model.materials.names() == []


def test_materials_names_returns_list(make_model) -> None:
    h = make_model({"PropMaterial.GetNameList": (2, ("C40", "S355"), 0)})

    assert h.model.materials.names() == ["C40", "S355"]


# -- frame sections ---------------------------------------------------------


def test_add_rectangle_args(make_model) -> None:
    h = make_model({"PropFrame.SetRectangle": 0})
    h.model.frame_sections.add_rectangle("R", material="C40", depth=2.0, width=1.0)
    (args,) = h.called("PropFrame.SetRectangle")
    assert args == ("R", "C40", 2.0, 1.0, -1, "", "")


def test_add_circle_returns_handle_and_passes_args(make_model) -> None:
    h = make_model({"PropFrame.SetCircle": 0})

    section = h.model.frame_sections.add_circle(
        "CIRC",
        material="C40",
        diameter=0.75,
        notes="solid",
    )

    assert isinstance(section, FrameSectionHandle)
    assert section.name == "CIRC"
    assert section._owner is h.model.frame_sections
    assert h.called("PropFrame.SetCircle") == [("CIRC", "C40", 0.75, -1, "solid", "")]


def test_add_general_returns_handle_and_passes_args(make_model) -> None:
    h = make_model({"PropFrame.SetGeneral": 0})

    section = h.model.frame_sections.add_general(
        "GEN",
        material=h.model.materials.ref("C40"),
        depth=2,
        width=1,
        area=1.5,
        as2=0.8,
        as3=0.9,
        torsion=0.12,
        i22=0.21,
        i33=0.34,
        notes="explicit",
    )

    assert isinstance(section, FrameSectionHandle)
    assert section.name == "GEN"
    assert section._owner is h.model.frame_sections
    assert h.called("PropFrame.SetGeneral") == [
        (
            "GEN",
            "C40",
            2.0,
            1.0,
            1.5,
            0.8,
            0.9,
            0.12,
            0.21,
            0.34,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            -1,
            "explicit",
            "",
        )
    ]


def test_add_rectangle_rejects_foreign_material_handle(make_model) -> None:
    h1 = make_model({"PropFrame.SetRectangle": 0})
    h2 = make_model()
    foreign_material = h2.model.materials.ref("C40")
    with pytest.raises(ValueError, match="another manager/model"):
        h1.model.frame_sections.add_rectangle("R", material=foreign_material, depth=2.0, width=1.0)
    assert h1.called("PropFrame.SetRectangle") == []


def test_frame_section_handle_set_modifiers_validates_length(make_model) -> None:
    h = make_model({"PropFrame.SetModifiers": 0})
    with pytest.raises(ValueError, match="8 elements"):
        h.model.frame_sections.ref("R").set_modifiers([1.0, 1.0])


def test_frame_section_handle_delete_passes_name(make_model) -> None:
    h = make_model({"PropFrame.Delete": 0})

    h.model.frame_sections.ref("R").delete()

    assert h.called("PropFrame.Delete") == [("R",)]


def test_frame_sections_names_empty_model(make_model) -> None:
    h = make_model({"PropFrame.GetNameList": (0, None, 0)})

    assert h.model.frame_sections.names() == []


def test_frame_sections_names_returns_list(make_model) -> None:
    h = make_model({"PropFrame.GetNameList": (2, ("R1", "CIRC"), 0)})

    assert h.model.frame_sections.names() == ["R1", "CIRC"]


# -- frames -----------------------------------------------------------------


def test_add_by_points_returns_handle(make_model) -> None:
    h = make_model(
        {
            "PointObj.GetNameList": (2, ("P1", "P2"), 0),
            "PropFrame.GetNameList": (1, ("R",), 0),
            "FrameObj.AddByPoint": ["F1", 0],
        }
    )
    f = h.model.frames.add_by_points("P1", "P2", section="R")
    assert isinstance(f, FrameHandle)
    assert f.name == "F1"
    (args,) = h.called("FrameObj.AddByPoint")
    assert args == ("P1", "P2", "", "R", "")


def test_add_by_points_rejects_foreign_point_handle(make_model) -> None:
    h1 = make_model({"FrameObj.AddByPoint": ["F1", 0]})
    h2 = make_model()
    foreign_point = h2.model.points.ref("P1")
    with pytest.raises(ValueError, match="another manager/model"):
        h1.model.frames.add_by_points(foreign_point, "P2", section="R")
    assert h1.called("FrameObj.AddByPoint") == []


def test_add_by_points_rejects_missing_point_name_before_com_call(make_model) -> None:
    h = make_model(
        {
            "PointObj.GetNameList": (1, ("P1",), 0),
            "PropFrame.GetNameList": (1, ("R",), 0),
            "FrameObj.AddByPoint": ["F1", 0],
        }
    )

    with pytest.raises(SapNameNotFoundError, match="No point named 'P2'"):
        h.model.frames.add_by_points("P1", "P2", section="R")

    assert h.called("FrameObj.AddByPoint") == []


def test_add_by_points_rejects_wrong_handle_type(make_model) -> None:
    h = make_model(
        {"PointObj.GetNameList": (2, ("P1", "P2"), 0), "FrameObj.AddByPoint": ["F1", 0]}
    )
    with pytest.raises(TypeError, match="expected PointHandle"):
        h.model.frames.add_by_points(FrameSectionHandle("P1"), "P2", section="R")
    with pytest.raises(TypeError, match="expected FrameSectionHandle"):
        h.model.frames.add_by_points(PointHandle("P1"), "P2", section=MaterialHandle("R"))
    assert h.called("FrameObj.AddByPoint") == []


def test_frame_handle_assign_section_accepts_string_and_handle(make_model) -> None:
    h = make_model({"FrameObj.SetSection": 0})
    f = h.model.frames.ref("F1")

    assert f.assign_section("R1") is f
    assert f.assign_section(h.model.frame_sections.ref("R2")) is f

    assert h.called("FrameObj.SetSection") == [
        ("F1", "R1", int(ItemType.OBJECT)),
        ("F1", "R2", int(ItemType.OBJECT)),
    ]


def test_frame_handle_rotate_passes_angle_and_itemtype(make_model) -> None:
    h = make_model({"FrameObj.SetLocalAxes": 0})
    f = h.model.frames.ref("F1")

    assert f.rotate(15) is f

    assert h.called("FrameObj.SetLocalAxes") == [("F1", 15.0, int(ItemType.OBJECT))]


def test_frame_handle_length_uses_endpoint_coordinates(make_model) -> None:
    def coord(name: str, *_args: object) -> tuple[float, float, float, int]:
        if name == "P1":
            return (0.0, 0.0, 0.0, 0)
        return (3.0, 4.0, 0.0, 0)

    h = make_model({"FrameObj.GetPoints": ("P1", "P2", 0), "PointObj.GetCoordCartesian": coord})

    assert h.model.frames.ref("F1").length == pytest.approx(5.0)
    assert h.called("FrameObj.GetPoints") == [("F1", "", "")]
    assert h.called("PointObj.GetCoordCartesian") == [
        ("P1", 0.0, 0.0, 0.0, "Global"),
        ("P2", 0.0, 0.0, 0.0, "Global"),
    ]


def test_frame_handle_delete_passes_name_and_itemtype(make_model) -> None:
    h = make_model({"FrameObj.Delete": 0})

    h.model.frames.ref("F1").delete()

    assert h.called("FrameObj.Delete") == [("F1", int(ItemType.OBJECT))]


def test_add_by_coord_returns_handle(make_model) -> None:
    h = make_model({"FrameObj.AddByCoord": ["F1", 0]})

    f = h.model.frames.add_by_coord(
        (0, 1, 2),
        (3, 4, 5),
        section=h.model.frame_sections.ref("R"),
        name="F-user",
        csys="Bridge",
    )

    assert isinstance(f, FrameHandle)
    assert f.name == "F1"
    assert h.called("FrameObj.AddByCoord") == [
        (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, "", "R", "F-user", "Bridge")
    ]


def test_add_by_coord_rejects_missing_section_name_before_com_call(make_model) -> None:
    h = make_model({"PropFrame.GetNameList": (1, ("R",), 0), "FrameObj.AddByCoord": ["F1", 0]})

    with pytest.raises(SapNameNotFoundError, match="No frame section named 'MISSING'"):
        h.model.frames.add_by_coord((0, 0, 0), (1, 0, 0), section="MISSING")

    assert h.called("FrameObj.AddByCoord") == []


def test_frames_count_uses_value_path(make_model) -> None:
    h = make_model({"FrameObj.Count": 3})

    assert h.model.frames.count() == 3


def test_frames_names_returns_list(make_model) -> None:
    h = make_model({"FrameObj.GetNameList": (2, ("F1", "F2"), 0)})

    assert h.model.frames.names() == ["F1", "F2"]


def test_frame_handle_release_validates_lengths(make_model) -> None:
    h = make_model({"FrameObj.SetReleases": 0})
    with pytest.raises(ValueError, match="6 elements"):
        h.model.frames.ref("F1").release(i_end=[True], j_end=[False] * 6)


def test_output_stations_requires_exactly_one(make_model) -> None:
    h = make_model({"GetVersion": ("25.0.0", 25.0, 0), "FrameObj.SetOutputStations": 0})
    with pytest.raises(ValueError, match="exactly one"):
        h.model.frames.ref("F1").set_output_stations()
    with pytest.raises(ValueError, match="exactly one"):
        h.model.frames.ref("F1").set_output_stations(min_stations=3, max_segment_size=1.0)


def test_output_stations_min_count(make_model) -> None:
    h = make_model({"GetVersion": ("25.0.0", 25.0, 0), "FrameObj.SetOutputStations": 0})
    h.model.frames.ref("F1").set_output_stations(min_stations=5)
    (args,) = h.called("FrameObj.SetOutputStations")
    # (name, myType=2, maxSeg=0.0, minSections=5, noOut, noOut, itemType)
    assert args == ("F1", 2, 0.0, 5, False, False, 0)


def test_output_stations_max_segment(make_model) -> None:
    h = make_model({"GetVersion": ("25.0.0", 25.0, 0), "FrameObj.SetOutputStations": 0})
    h.model.frames.ref("F1").set_output_stations(max_segment_size=0.5)
    (args,) = h.called("FrameObj.SetOutputStations")
    assert args == ("F1", 1, 0.5, 2, False, False, 0)


# -- constraints ------------------------------------------------------------


def test_constraints_add_body_defaults_to_all_dof(make_model) -> None:
    h = make_model({"ConstraintDef.SetBody": 0})

    assert h.model.constraints.add_body("BODY") == "BODY"

    assert h.called("ConstraintDef.SetBody") == [("BODY", [True] * 6, "Global")]


def test_constraints_add_body_accepts_explicit_dof_and_csys(make_model) -> None:
    h = make_model({"ConstraintDef.SetBody": 0})

    assert h.model.constraints.add_body("BODY", dof=("U1", "R3"), csys="Local") == "BODY"

    assert h.called("ConstraintDef.SetBody") == [
        ("BODY", [True, False, False, False, False, True], "Local")
    ]


def test_constraints_add_equal_defaults_to_all_dof(make_model) -> None:
    h = make_model({"ConstraintDef.SetEqual": 0})

    assert h.model.constraints.add_equal("EQ") == "EQ"

    assert h.called("ConstraintDef.SetEqual") == [("EQ", [True] * 6, "Global")]


def test_constraints_add_equal_accepts_explicit_dof_and_csys(make_model) -> None:
    h = make_model({"ConstraintDef.SetEqual": 0})

    assert h.model.constraints.add_equal("EQ", dof=("U2", "R1"), csys="Joint") == "EQ"

    assert h.called("ConstraintDef.SetEqual") == [
        ("EQ", [False, True, False, True, False, False], "Joint")
    ]


def test_constraints_names_empty_model(make_model) -> None:
    h = make_model({"ConstraintDef.GetNameList": (0, None, 0)})

    assert h.model.constraints.names() == []


def test_constraints_names_returns_list(make_model) -> None:
    h = make_model({"ConstraintDef.GetNameList": (2, ("BODY", "EQ"), 0)})

    assert h.model.constraints.names() == ["BODY", "EQ"]


def test_manager_without_handle_class_rejects_handle_queries_before_name_lookup(make_model) -> None:
    h = make_model({"ConstraintDef.GetNameList": (1, ("BODY",), 0)})

    with pytest.raises(TypeError, match="Constraints does not define a handle class"):
        h.model.constraints.get("BODY")
    with pytest.raises(TypeError, match="Constraints does not define a handle class"):
        h.model.constraints["MISSING"]
    with pytest.raises(TypeError, match="Constraints does not define a handle class"):
        h.model.constraints.all()
    with pytest.raises(TypeError, match="Constraints does not define a handle class"):
        h.model.constraints.ref("BODY")

    assert h.called("ConstraintDef.GetNameList") == []


def test_constraints_delete_passes_name(make_model) -> None:
    h = make_model({"ConstraintDef.Delete": 0})

    h.model.constraints.delete("BODY")

    assert h.called("ConstraintDef.Delete") == [("BODY",)]


# -- links ------------------------------------------------------------------


def test_link_props_add_linear_returns_handle_and_passes_args(make_model) -> None:
    h = make_model({"PropLink.SetLinear": 0})

    prop = h.model.link_props.add_linear(
        "LP1",
        [1, 2, 3, 4, 5, 6],
        damping=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        dof=["U1", "R3"],
        fixed="U1",
        notes="bearing",
    )

    assert isinstance(prop, LinkPropHandle)
    assert prop.name == "LP1"
    assert prop._owner is h.model.link_props
    assert h.called("PropLink.SetLinear") == [
        (
            "LP1",
            [True, False, False, False, False, True],
            [True, False, False, False, False, False],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            0.0,
            0.0,
            False,
            False,
            "bearing",
            "",
        )
    ]


def test_link_props_add_linear_validates_lengths(make_model) -> None:
    h = make_model({"PropLink.SetLinear": 0})

    with pytest.raises(ValueError, match="stiffness must have 6 elements"):
        h.model.link_props.add_linear("LP1", [1.0, 2.0])
    with pytest.raises(ValueError, match="damping must have 6 elements"):
        h.model.link_props.add_linear("LP1", [1.0] * 6, damping=[1.0])

    assert h.called("PropLink.SetLinear") == []


def test_link_props_names_returns_list(make_model) -> None:
    h = make_model({"PropLink.GetNameList": (2, ("LP1", "LP2"), 0)})

    assert h.model.link_props.names() == ["LP1", "LP2"]


def test_link_prop_handle_delete_passes_name(make_model) -> None:
    h = make_model({"PropLink.Delete": 0})

    h.model.link_props.ref("LP1").delete()

    assert h.called("PropLink.Delete") == [("LP1",)]


def test_links_add_by_points_returns_handle_and_passes_args(make_model) -> None:
    h = make_model(
        {"PointObj.GetNameList": (2, ("P1", "P2"), 0), "LinkObj.AddByPoint": ["L1", 0]}
    )

    link = h.model.links.add_by_points(
        h.model.points.ref("P1"),
        "P2",
        h.model.link_props.ref("LP1"),
        name="L-user",
        single_joint=True,
    )

    assert isinstance(link, LinkHandle)
    assert link.name == "L1"
    assert h.called("LinkObj.AddByPoint") == [
        ("P1", "P2", "", True, "LP1", "L-user")
    ]


def test_links_add_by_points_rejects_wrong_handle_type(make_model) -> None:
    h = make_model(
        {"PointObj.GetNameList": (2, ("P1", "P2"), 0), "LinkObj.AddByPoint": ["L1", 0]}
    )

    with pytest.raises(TypeError, match="expected PointHandle"):
        h.model.links.add_by_points(FrameHandle("P1"), "P2", "LP1")
    with pytest.raises(TypeError, match="expected LinkPropHandle"):
        h.model.links.add_by_points("P1", "P2", FrameSectionHandle("LP1"))

    assert h.called("LinkObj.AddByPoint") == []


def test_link_handle_delete_passes_name(make_model) -> None:
    h = make_model({"LinkObj.Delete": 0})

    h.model.links.ref("L1").delete()

    assert h.called("LinkObj.Delete") == [("L1",)]


def test_links_count_uses_value_path(make_model) -> None:
    h = make_model({"LinkObj.Count": 4})

    assert h.model.links.count() == 4


def test_links_names_returns_list(make_model) -> None:
    h = make_model({"LinkObj.GetNameList": (2, ("L1", "L2"), 0)})

    assert h.model.links.names() == ["L1", "L2"]


# -- loads ------------------------------------------------------------------


def test_load_pattern_add(make_model) -> None:
    h = make_model({"LoadPatterns.Add": 0})
    h.model.loads.patterns.add("WIND", pattern_type=LoadPatternType.WIND, self_weight=0.0)
    assert h.called("LoadPatterns.Add") == [("WIND", int(LoadPatternType.WIND), 0.0, True)]


def test_load_pattern_set_self_weight(make_model) -> None:
    h = make_model({"LoadPatterns.SetSelfWTMultiplier": 0})
    h.model.loads.patterns.set_self_weight("DEAD", 1.0)
    assert h.called("LoadPatterns.SetSelfWTMultiplier") == [("DEAD", 1.0)]


def test_static_linear_with_loads(make_model) -> None:
    h = make_model({"LoadCases.StaticLinear.SetCase": 0, "LoadCases.StaticLinear.SetLoads": 0})
    h.model.loads.cases.add_static_linear("LC", loads={"DEAD": 1.0, "LIVE": 0.5})
    (args,) = h.called("LoadCases.StaticLinear.SetLoads")
    assert args == ("LC", 2, ["Load", "Load"], ["DEAD", "LIVE"], [1.0, 0.5])


def test_modal_eigen_sets_modes(make_model) -> None:
    h = make_model({"LoadCases.ModalEigen.SetCase": 0, "LoadCases.ModalEigen.SetNumberModes": 0})
    h.model.loads.cases.add_modal_eigen("MODAL", num_modes=10)
    assert h.called("LoadCases.ModalEigen.SetNumberModes") == [("MODAL", 10, 1)]


# -- analysis ---------------------------------------------------------------


def _status(*pairs: tuple[str, int]):
    names = tuple(n for n, _ in pairs)
    codes = tuple(c for _, c in pairs)
    return (len(pairs), names, codes, 0)


def test_run_all_finished(make_model) -> None:
    h = make_model(
        {
            "GetModelFilename": "m.sdb",
            "Analyze.SetRunCaseFlag": 0,
            "Analyze.RunAnalysis": 0,
            "Analyze.GetCaseStatus": _status(("DEAD", 4), ("MODAL", 4)),
        }
    )
    report = h.model.analysis.run(cases=["MODAL"])
    assert report.all_finished
    # all cases turned off, then MODAL turned on
    assert ("", False, True) in h.called("Analyze.SetRunCaseFlag")
    assert ("MODAL", True, False) in h.called("Analyze.SetRunCaseFlag")


def test_run_raises_when_requested_case_unfinished(make_model) -> None:
    h = make_model(
        {
            "GetModelFilename": "m.sdb",
            "Analyze.SetRunCaseFlag": 0,
            "Analyze.RunAnalysis": 0,
            "Analyze.GetCaseStatus": _status(("MODAL", 3)),  # not finished
        }
    )
    with pytest.raises(SapAnalysisError):
        h.model.analysis.run(cases=["MODAL"])


def test_run_requires_saved_model(make_model) -> None:
    h = make_model({"GetModelFilename": ""})  # not saved
    with pytest.raises(SapError, match="must be saved"):
        h.model.analysis.run(cases=["MODAL"])


# -- results ----------------------------------------------------------------


def test_modal_periods_table(make_model) -> None:
    h = make_model(
        {
            "Results.ModalPeriod": (
                2,
                ("MODAL", "MODAL"),
                ("Mode", "Mode"),
                (1, 2),
                (0.5, 0.3),
                (2.0, 3.33),
                (12.6, 20.9),
                (158.0, 437.0),
                0,
            )
        }
    )
    table = h.model.results.modal_periods()
    assert isinstance(table, ResultTable)
    assert len(table) == 2
    assert table["period"] == (0.5, 0.3)
    assert table["mode"] == (1, 2)


def _frame_force_result(frame: str = "F1"):
    return (
        1,
        (frame,),
        (0.0,),
        ("E1",),
        (0.0,),
        ("DEAD",),
        ("Step",),
        (0.0,),
        (1.0,),
        (2.0,),
        (3.0,),
        (4.0,),
        (5.0,),
        (6.0,),
        0,
    )


def _frame_force_result_many(*frames: str):
    count = len(frames)
    return (
        count,
        tuple(frames),
        (0.0,) * count,
        ("E1",) * count,
        (0.0,) * count,
        ("DEAD",) * count,
        ("Step",) * count,
        (0.0,) * count,
        (1.0,) * count,
        (2.0,) * count,
        (3.0,) * count,
        (4.0,) * count,
        (5.0,) * count,
        (6.0,) * count,
        0,
    )


def _joint_react_result(point: str = "P1"):
    return (
        1,
        (point,),
        ("E1",),
        ("DEAD",),
        ("Step",),
        (0.0,),
        (1.0,),
        (2.0,),
        (3.0,),
        (4.0,),
        (5.0,),
        (6.0,),
        0,
    )


def _joint_result_many(*points: str):
    count = len(points)
    return (
        count,
        tuple(points),
        ("E1",) * count,
        ("DEAD",) * count,
        ("Step",) * count,
        (0.0,) * count,
        (1.0,) * count,
        (2.0,) * count,
        (3.0,) * count,
        (4.0,) * count,
        (5.0,) * count,
        (6.0,) * count,
        0,
    )


def _joint_displ_result(point: str = "P1"):
    return (
        1,
        (point,),
        ("E1",),
        ("DEAD",),
        ("Step",),
        (0.0,),
        (1.0,),
        (2.0,),
        (3.0,),
        (4.0,),
        (5.0,),
        (6.0,),
        0,
    )


def _selected_output_responses(selected: bool = True) -> dict[str, object]:
    return {
        "LoadCases.GetNameList": (1, ("DEAD",), 0),
        "Results.Setup.GetCaseSelectedForOutput": (selected, 0),
        "RespCombo.GetNameList": (0, (), 0),
    }


def test_frame_forces_rejects_foreign_frame_handle(make_model) -> None:
    h1 = make_model({"Results.FrameForce": _frame_force_result()})
    h2 = make_model()
    foreign = h2.model.frames.ref("F1")
    with pytest.raises(ValueError, match="another manager/model"):
        h1.model.results.frame_forces(foreign)
    assert h1.called("Results.FrameForce") == []


def test_frame_handle_forces_does_not_select_output(make_model) -> None:
    h = make_model({**_selected_output_responses(), "Results.FrameForce": _frame_force_result()})
    table = h.model.frames.ref("F1").forces()
    assert table["P"] == (1.0,)
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == []
    assert h.called("LoadCases.GetNameList") == []
    assert h.called("Results.FrameForce") == [("F1", int(ItemTypeElm.OBJECT_ELM))]


def test_frame_handle_forces_without_selected_output_has_actionable_error(make_model) -> None:
    h = make_model({**_selected_output_responses(selected=False), "Results.FrameForce": 1})
    with pytest.raises(SapApiError, match="select_output") as info:
        h.model.frames.ref("F1").forces()
    assert info.value.api_name == "Results.FrameForce"
    assert info.value.args_passed == ("F1", int(ItemTypeElm.OBJECT_ELM))
    assert h.called("Results.FrameForce") == [("F1", int(ItemTypeElm.OBJECT_ELM))]
    assert h.called("LoadCases.GetNameList") == [()]


def test_frame_handle_forces_keeps_original_error_when_output_is_selected(make_model) -> None:
    h = make_model({**_selected_output_responses(), "Results.FrameForce": 7})
    with pytest.raises(SapApiError, match="status 7") as info:
        h.model.frames.ref("F1").forces()
    assert info.value.hint == ""
    assert h.called("Results.FrameForce") == [("F1", int(ItemTypeElm.OBJECT_ELM))]
    assert h.called("LoadCases.GetNameList") == [()]


def test_frame_handle_forces_keeps_original_error_when_output_probe_fails(make_model) -> None:
    h = make_model({"Results.FrameForce": 7, "LoadCases.GetNameList": 3})
    with pytest.raises(SapApiError, match="status 7") as info:
        h.model.frames.ref("F1").forces()

    assert info.value.api_name == "Results.FrameForce"
    assert info.value.hint == ""
    assert "LoadCases.GetNameList" not in str(info.value)
    assert h.called("Results.FrameForce") == [("F1", int(ItemTypeElm.OBJECT_ELM))]
    assert h.called("LoadCases.GetNameList") == [()]


def test_frame_handle_forces_keeps_original_error_when_combo_output_is_selected(
    make_model,
) -> None:
    h = make_model(
        {
            "Results.FrameForce": 7,
            "LoadCases.GetNameList": (0, (), 0),
            "RespCombo.GetNameList": (1, ("COMB1",), 0),
            "Results.Setup.GetComboSelectedForOutput": (True, 0),
        }
    )

    with pytest.raises(SapApiError, match="status 7") as info:
        h.model.frames.ref("F1").forces()

    assert info.value.hint == ""
    assert h.called("Results.FrameForce") == [("F1", int(ItemTypeElm.OBJECT_ELM))]
    assert h.called("LoadCases.GetNameList") == [()]
    assert h.called("RespCombo.GetNameList") == [()]
    assert h.called("Results.Setup.GetComboSelectedForOutput") == [("COMB1", False)]


def test_result_batch_group_is_lazy_and_does_not_select_when_cases_omitted(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "GroupDef.GetNameList": (1, ("G1",), 0),
            "Results.FrameForce": _frame_force_result("G1"),
        }
    )
    plan = h.model.results.batch().frame_forces(group="G1", key="forces")
    assert h.calls == []

    tables = plan.collect()

    assert tables["forces"]["P"] == (1.0,)
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == []
    assert h.called("Results.FrameForce") == [("G1", int(ItemTypeElm.GROUP_ELM))]


def test_result_batch_group_target_rejects_empty_result_table(make_model) -> None:
    h = make_model(
        {
            "GroupDef.GetNameList": (1, ("empty",), 0),
            "Results.JointReact": _joint_result_many(),
        }
    )

    with pytest.raises(ValueError, match="group target 'empty'"):
        h.model.results.batch().joint_reactions(group="empty", key="reactions").collect()

    assert h.called("Results.JointReact") == [("empty", int(ItemTypeElm.GROUP_ELM))]


def test_result_batch_temporarily_selects_output_when_cases_are_given(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "GroupDef.GetNameList": (2, ("G1", "supports"), 0),
            "Results.Setup.DeselectAllCasesAndCombosForOutput": 0,
            "Results.Setup.SetCaseSelectedForOutput": 0,
            "Results.FrameForce": _frame_force_result("G1"),
            "Results.JointReact": _joint_react_result("supports"),
        }
    )
    tables = (
        h.model.results.batch(cases=["DEAD"])
        .frame_forces(group="G1", key="forces")
        .joint_reactions(group="supports", key="reactions")
        .collect()
    )

    assert set(tables) == {"forces", "reactions"}
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == [(), ()]
    assert h.called("Results.Setup.SetCaseSelectedForOutput") == [("DEAD", True), ("DEAD", True)]
    assert h.called("Results.FrameForce") == [("G1", int(ItemTypeElm.GROUP_ELM))]
    assert h.called("Results.JointReact") == [("supports", int(ItemTypeElm.GROUP_ELM))]


def test_result_batch_restores_selected_output_between_batches_and_single_read(make_model) -> None:
    selected_cases = {"BASE"}

    def deselect_output() -> int:
        selected_cases.clear()
        return 0

    def set_case_output(case: str, selected: bool) -> int:
        if selected:
            selected_cases.add(case)
        else:
            selected_cases.discard(case)
        return 0

    def get_case_output(case: str, _selected: bool) -> tuple[bool, int]:
        return case in selected_cases, 0

    def frame_force(name: str, _item_type: int) -> tuple[object, ...]:
        case = next(iter(selected_cases)) if selected_cases else "NONE"
        result = list(_frame_force_result(name))
        result[5] = (case,)
        return tuple(result)

    h = make_model(
        {
            "LoadCases.GetNameList": (3, ("BASE", "DEAD", "LIVE"), 0),
            "Results.Setup.GetCaseSelectedForOutput": get_case_output,
            "RespCombo.GetNameList": (0, (), 0),
            "Results.Setup.DeselectAllCasesAndCombosForOutput": deselect_output,
            "Results.Setup.SetCaseSelectedForOutput": set_case_output,
            "FrameObj.GetNameList": (1, ("F1",), 0),
            "Results.FrameForce": frame_force,
        }
    )

    dead = h.model.results.batch(cases=["DEAD"]).frame_forces(frames=["F1"]).collect()
    assert dead["frame_forces"]["case"] == ("DEAD",)
    assert selected_cases == {"BASE"}

    live = h.model.results.batch(cases=["LIVE"]).frame_forces(frames=["F1"]).collect()
    assert live["frame_forces"]["case"] == ("LIVE",)
    assert selected_cases == {"BASE"}

    single = h.model.frames.ref("F1").forces()
    assert single["case"] == ("BASE",)


def test_result_batch_restores_selected_output_when_temporary_selection_fails(make_model) -> None:
    selected_cases = {"BASE"}

    def deselect_output() -> int:
        selected_cases.clear()
        return 0

    def set_case_output(case: str, selected: bool) -> int:
        if selected and case == "LIVE":
            return 7
        if selected:
            selected_cases.add(case)
        else:
            selected_cases.discard(case)
        return 0

    def get_case_output(case: str, _selected: bool) -> tuple[bool, int]:
        return case in selected_cases, 0

    h = make_model(
        {
            "LoadCases.GetNameList": (3, ("BASE", "DEAD", "LIVE"), 0),
            "Results.Setup.GetCaseSelectedForOutput": get_case_output,
            "RespCombo.GetNameList": (0, (), 0),
            "Results.Setup.DeselectAllCasesAndCombosForOutput": deselect_output,
            "Results.Setup.SetCaseSelectedForOutput": set_case_output,
        }
    )

    with pytest.raises(SapApiError, match="SetCaseSelectedForOutput"):
        h.model.results.batch(cases=["DEAD", "LIVE"]).modal_periods().collect()

    assert selected_cases == {"BASE"}
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == [(), ()]
    assert h.called("Results.Setup.SetCaseSelectedForOutput") == [
        ("DEAD", True),
        ("LIVE", True),
        ("BASE", True),
    ]
    assert h.called("Results.ModalPeriod") == []


def test_result_batch_modal_periods_uses_default_key_and_combo_selection(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(selected=False),
            "Results.Setup.DeselectAllCasesAndCombosForOutput": 0,
            "Results.Setup.SetComboSelectedForOutput": 0,
            "Results.ModalPeriod": (
                1,
                ("MODAL",),
                ("Mode",),
                (1,),
                (0.5,),
                (2.0,),
                (12.6,),
                (158.0,),
                0,
            ),
        }
    )

    tables = h.model.results.batch(combos=["COMB1"]).modal_periods().collect()

    assert set(tables) == {"modal_periods"}
    assert tables["modal_periods"]["mode"] == (1,)
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == [(), ()]
    assert h.called("Results.Setup.SetCaseSelectedForOutput") == []
    assert h.called("Results.Setup.SetComboSelectedForOutput") == [("COMB1", True)]


def test_result_batch_rejects_duplicate_default_keys(make_model) -> None:
    h = make_model()

    with pytest.raises(ValueError, match="duplicate result batch key 'modal_periods'"):
        h.model.results.batch().modal_periods().modal_periods()


def test_result_batch_selection_reads_current_sap_selection_without_mutating_it(make_model) -> None:
    h = make_model(
        {**_selected_output_responses(), "Results.FrameForce": _frame_force_result("F1")}
    )
    h.model.results.batch().frame_forces(selection=True, key="selected").collect()
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == []
    assert h.called("Results.FrameForce") == [("", int(ItemTypeElm.SELECTION_ELM))]


def test_result_batch_frames_default_to_object_reads_without_temp_group(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "FrameObj.GetNameList": (2, ("F1", "F2"), 0),
            "Results.FrameForce": lambda name, _item_type: _frame_force_result(name),
        }
    )
    tables = h.model.results.batch().frame_forces(frames=["F1", "F2"], key="forces").collect()

    assert tables["forces"]["frame"] == ("F1", "F2")
    assert h.called("Results.FrameForce") == [
        ("F1", int(ItemTypeElm.OBJECT_ELM)),
        ("F2", int(ItemTypeElm.OBJECT_ELM)),
    ]
    assert h.called("GroupDef.SetGroup") == []
    assert h.called("GroupDef.Delete") == []


def test_result_batch_rejects_missing_frame_target_before_read(make_model) -> None:
    h = make_model(
        {
            "FrameObj.GetNameList": (1, ("F1",), 0),
            "Results.FrameForce": lambda name, _item_type: _frame_force_result(name),
        }
    )

    with pytest.raises(SapNameNotFoundError, match="No frame named 'F2'"):
        h.model.results.batch().frame_forces(frames=["F1", "F2"], key="forces").collect()

    assert h.called("Results.FrameForce") == []


def test_result_batch_rejects_missing_rows_for_requested_target(make_model) -> None:
    def frame_force(name: str, _item_type: int) -> tuple[object, ...]:
        if name == "F2":
            return (0, (), (), (), (), (), (), (), (), (), (), (), (), (), 0)
        return _frame_force_result(name)

    h = make_model(
        {
            "FrameObj.GetNameList": (2, ("F1", "F2"), 0),
            "Results.FrameForce": frame_force,
        }
    )

    with pytest.raises(ValueError, match="F2"):
        h.model.results.batch().frame_forces(frames=["F1", "F2"], key="forces").collect()

    assert h.called("Results.FrameForce") == [
        ("F1", int(ItemTypeElm.OBJECT_ELM)),
        ("F2", int(ItemTypeElm.OBJECT_ELM)),
    ]


def test_result_batch_rejects_missing_or_ambiguous_single_target(make_model) -> None:
    h = make_model()

    with pytest.raises(ValueError, match="provide exactly one result target"):
        h.model.results.batch().frame_forces()
    with pytest.raises(ValueError, match="provide exactly one result target"):
        h.model.results.batch().frame_forces(frame="F1", group="G1")


def test_result_batch_rejects_unknown_strategy(make_model) -> None:
    h = make_model()
    with pytest.raises(ValueError, match="strategy"):
        h.model.results.batch().frame_forces(
            frames=["F1"],
            strategy="typo",  # type: ignore[arg-type]
        )


def test_result_batch_frames_temporary_group_is_explicit_opt_in(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "FrameObj.GetNameList": (2, ("F1", "F2"), 0),
            "GroupDef.SetGroup": 0,
            "FrameObj.SetGroupAssign": 0,
            "GroupDef.Delete": 0,
            "Results.FrameForce": lambda _name, _item_type: _frame_force_result_many("F1", "F2"),
        }
    )

    tables = (
        h.model.results.batch()
        .frame_forces(frames=["F1", "F2"], key="forces", strategy="temporary_group")
        .collect()
    )

    assert tables["forces"]["frame"] == ("F1", "F2")
    (group_name,) = h.called("GroupDef.SetGroup")[0]
    assert group_name.startswith("__sap2000py_results_")
    assert h.called("FrameObj.SetGroupAssign") == [
        ("F1", group_name, False, 0),
        ("F2", group_name, False, 0),
    ]
    assert h.called("Results.FrameForce") == [(group_name, int(ItemTypeElm.GROUP_ELM))]
    assert h.called("GroupDef.Delete") == [(group_name,)]


def test_result_batch_temporary_group_is_deleted_when_read_fails(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(selected=False),
            "FrameObj.GetNameList": (2, ("F1", "F2"), 0),
            "GroupDef.SetGroup": 0,
            "FrameObj.SetGroupAssign": 0,
            "GroupDef.Delete": 0,
            "Results.FrameForce": 1,
        }
    )

    with pytest.raises(SapApiError, match="select_output"):
        (
            h.model.results.batch()
            .frame_forces(frames=["F1", "F2"], key="forces", strategy="temporary_group")
            .collect()
        )

    (group_name,) = h.called("GroupDef.SetGroup")[0]
    assert h.called("GroupDef.Delete") == [(group_name,)]


def test_result_batch_joint_displacement_single_target_uses_object_read(make_model) -> None:
    h = make_model(
        {"PointObj.GetNameList": (1, ("P1",), 0), "Results.JointDispl": _joint_displ_result("P1")}
    )

    tables = h.model.results.batch().joint_displacements(point="P1", key="displ").collect()

    assert tables["displ"]["U1"] == (1.0,)
    assert h.called("Results.JointDispl") == [("P1", int(ItemTypeElm.OBJECT_ELM))]
    assert h.called("GroupDef.SetGroup") == []


def test_result_batch_points_default_to_object_reads_without_temp_group(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "PointObj.GetNameList": (2, ("P1", "P2"), 0),
            "Results.JointReact": lambda name, _item_type: _joint_react_result(name),
        }
    )

    tables = h.model.results.batch().joint_reactions(points=["P1", "P2"], key="reactions").collect()

    assert tables["reactions"]["joint"] == ("P1", "P2")
    assert h.called("Results.JointReact") == [
        ("P1", int(ItemTypeElm.OBJECT_ELM)),
        ("P2", int(ItemTypeElm.OBJECT_ELM)),
    ]
    assert h.called("GroupDef.SetGroup") == []
    assert h.called("GroupDef.Delete") == []


def test_result_batch_point_reactions_temporary_group_is_explicit_opt_in(make_model) -> None:
    h = make_model(
        {
            "PointObj.GetNameList": (2, ("P1", "P2"), 0),
            "GroupDef.SetGroup": 0,
            "PointObj.SetGroupAssign": 0,
            "GroupDef.Delete": 0,
            "Results.JointReact": lambda _name, _item_type: _joint_result_many("P1", "P2"),
        }
    )

    tables = (
        h.model.results.batch()
        .joint_reactions(points=["P1", "P2"], key="reactions", strategy="temporary_group")
        .collect()
    )

    assert tables["reactions"]["joint"] == ("P1", "P2")
    (group_name,) = h.called("GroupDef.SetGroup")[0]
    assert group_name.startswith("__sap2000py_results_")
    assert h.called("PointObj.SetGroupAssign") == [
        ("P1", group_name, False, 0),
        ("P2", group_name, False, 0),
    ]
    assert h.called("Results.JointReact") == [(group_name, int(ItemTypeElm.GROUP_ELM))]
    assert h.called("GroupDef.Delete") == [(group_name,)]


def test_result_batch_points_temporary_group_is_explicit_opt_in(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "PointObj.GetNameList": (2, ("P1", "P2"), 0),
            "GroupDef.SetGroup": 0,
            "PointObj.SetGroupAssign": 0,
            "GroupDef.Delete": 0,
            "Results.JointDispl": lambda _name, _item_type: _joint_result_many("P1", "P2"),
        }
    )

    tables = (
        h.model.results.batch()
        .joint_displacements(points=["P1", "P2"], key="displ", strategy="temporary_group")
        .collect()
    )

    assert tables["displ"]["joint"] == ("P1", "P2")
    (group_name,) = h.called("GroupDef.SetGroup")[0]
    assert group_name.startswith("__sap2000py_results_")
    assert h.called("PointObj.SetGroupAssign") == [
        ("P1", group_name, False, 0),
        ("P2", group_name, False, 0),
    ]
    assert h.called("Results.JointDispl") == [(group_name, int(ItemTypeElm.GROUP_ELM))]
    assert h.called("GroupDef.Delete") == [(group_name,)]


def test_result_table_rows_and_empty() -> None:
    table = ResultTable({"a": (1, 2), "b": ("x", "y")})
    assert table.names == ["a", "b"]
    assert table.rows() == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    assert len(ResultTable({})) == 0


def test_result_table_to_pandas() -> None:
    pd = pytest.importorskip("pandas")
    table = ResultTable({"period": (0.5, 0.3)})
    df = table.to_pandas()
    assert isinstance(df, pd.DataFrame)
    assert list(df["period"]) == [0.5, 0.3]


# -- groups -----------------------------------------------------------------


def test_group_add_and_frame_assignment(make_model) -> None:
    h = make_model({"GroupDef.SetGroup": 0, "FrameObj.SetGroupAssign": 0})
    g = h.model.groups.add("piers")
    h.model.frames.ref("F1").group(g)
    assert h.called("GroupDef.SetGroup") == [("piers",)]
    assert h.called("FrameObj.SetGroupAssign") == [("F1", "piers", False, 0)]


def test_point_group_assignment(make_model) -> None:
    h = make_model({"GroupDef.SetGroup": 0, "PointObj.SetGroupAssign": 0})
    g = h.model.groups.add("supports")
    p = h.model.points.ref("P1")
    assert p.group(g) is p
    assert h.called("GroupDef.SetGroup") == [("supports",)]
    assert h.called("PointObj.SetGroupAssign") == [("P1", "supports", False, 0)]


def test_group_handle_delete_passes_name(make_model) -> None:
    h = make_model({"GroupDef.Delete": 0})

    h.model.groups.ref("supports").delete()

    assert h.called("GroupDef.Delete") == [("supports",)]


def test_groups_names_empty_model(make_model) -> None:
    h = make_model({"GroupDef.GetNameList": (0, None, 0)})

    assert h.model.groups.names() == []


def test_groups_names_returns_list(make_model) -> None:
    h = make_model({"GroupDef.GetNameList": (2, ("piers", "supports"), 0)})

    assert h.model.groups.names() == ["piers", "supports"]
