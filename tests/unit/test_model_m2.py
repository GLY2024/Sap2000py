"""Unit tests for the M2 typed managers over a fake COM tree."""

from __future__ import annotations

import pytest

from sap2000py import FrameHandle, FrameSectionHandle, MaterialHandle, PointHandle
from sap2000py.enums import ItemTypeElm, LoadPatternType, MatType
from sap2000py.errors import SapAnalysisError, SapApiError, SapError
from sap2000py.model.results import ResultTable

# -- materials --------------------------------------------------------------


def test_add_concrete_builds_grade_string_and_renames(make_model) -> None:
    h = make_model({"PropMaterial.AddMaterial": ["JTG-C40", 0], "PropMaterial.ChangeName": 0})
    mat = h.model.materials.add_concrete("C40", grade="C40", code="JTG")
    assert isinstance(mat, MaterialHandle)
    assert mat.name == "C40"
    (add_args,) = h.called("PropMaterial.AddMaterial")
    assert add_args == ("", int(MatType.CONCRETE), "China", "JTG", "JTG D62-2004 C40")
    assert h.called("PropMaterial.ChangeName") == [("JTG-C40", "C40")]


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


# -- frame sections ---------------------------------------------------------


def test_add_rectangle_args(make_model) -> None:
    h = make_model({"PropFrame.SetRectangle": 0})
    h.model.frame_sections.add_rectangle("R", material="C40", depth=2.0, width=1.0)
    (args,) = h.called("PropFrame.SetRectangle")
    assert args == ("R", "C40", 2.0, 1.0, -1, "", "")


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


# -- frames -----------------------------------------------------------------


def test_add_by_points_returns_handle(make_model) -> None:
    h = make_model({"FrameObj.AddByPoint": ["F1", 0]})
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


def test_add_by_points_rejects_wrong_handle_type(make_model) -> None:
    h = make_model({"FrameObj.AddByPoint": ["F1", 0]})
    with pytest.raises(TypeError, match="expected PointHandle"):
        h.model.frames.add_by_points(FrameSectionHandle("P1"), "P2", section="R")
    with pytest.raises(TypeError, match="expected FrameSectionHandle"):
        h.model.frames.add_by_points(PointHandle("P1"), "P2", section=MaterialHandle("R"))
    assert h.called("FrameObj.AddByPoint") == []


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


def test_result_batch_group_is_lazy_and_does_not_select_when_cases_omitted(make_model) -> None:
    h = make_model(
        {**_selected_output_responses(), "Results.FrameForce": _frame_force_result("G1")}
    )
    plan = h.model.results.batch().frame_forces(group="G1", key="forces")
    assert h.calls == []

    tables = plan.collect()

    assert tables["forces"]["P"] == (1.0,)
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == []
    assert h.called("Results.FrameForce") == [("G1", int(ItemTypeElm.GROUP_ELM))]


def test_result_batch_selects_output_once_when_cases_are_given(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
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
    assert h.called("Results.Setup.DeselectAllCasesAndCombosForOutput") == [()]
    assert h.called("Results.Setup.SetCaseSelectedForOutput") == [("DEAD", True)]
    assert h.called("Results.FrameForce") == [("G1", int(ItemTypeElm.GROUP_ELM))]
    assert h.called("Results.JointReact") == [("supports", int(ItemTypeElm.GROUP_ELM))]


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
            "GroupDef.SetGroup": 0,
            "FrameObj.SetGroupAssign": 0,
            "GroupDef.Delete": 0,
            "Results.FrameForce": lambda name, _item_type: _frame_force_result(name),
        }
    )

    tables = (
        h.model.results.batch()
        .frame_forces(frames=["F1", "F2"], key="forces", strategy="temporary_group")
        .collect()
    )

    assert tables["forces"]["P"] == (1.0,)
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


def test_result_batch_points_default_to_object_reads_without_temp_group(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
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


def test_result_batch_points_temporary_group_is_explicit_opt_in(make_model) -> None:
    h = make_model(
        {
            **_selected_output_responses(),
            "GroupDef.SetGroup": 0,
            "PointObj.SetGroupAssign": 0,
            "GroupDef.Delete": 0,
            "Results.JointDispl": lambda name, _item_type: _joint_displ_result(name),
        }
    )

    tables = (
        h.model.results.batch()
        .joint_displacements(points=["P1", "P2"], key="displ", strategy="temporary_group")
        .collect()
    )

    assert tables["displ"]["U1"] == (1.0,)
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
