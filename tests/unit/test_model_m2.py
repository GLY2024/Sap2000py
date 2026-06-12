"""Unit tests for the M2 typed managers over a fake COM tree."""

from __future__ import annotations

import pytest

from sap2000py.enums import LoadPatternType, MatType
from sap2000py.errors import SapAnalysisError, SapError
from sap2000py.handles import FrameHandle, MaterialHandle
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


def test_set_modifiers_validates_length(make_model) -> None:
    h = make_model({"PropFrame.SetModifiers": 0})
    with pytest.raises(ValueError, match="8 elements"):
        h.model.frame_sections.set_modifiers("R", [1.0, 1.0])


# -- frames -----------------------------------------------------------------


def test_add_by_points_returns_handle(make_model) -> None:
    h = make_model({"FrameObj.AddByPoint": ["F1", 0]})
    f = h.model.frames.add_by_points("P1", "P2", section="R")
    assert isinstance(f, FrameHandle)
    assert f.name == "F1"
    (args,) = h.called("FrameObj.AddByPoint")
    assert args == ("P1", "P2", "", "R", "")


def test_set_releases_validates_lengths(make_model) -> None:
    h = make_model({"FrameObj.SetReleases": 0})
    with pytest.raises(ValueError, match="6 elements"):
        h.model.frames.set_releases("F1", i_end=[True], j_end=[False] * 6)


def test_output_stations_requires_exactly_one(make_model) -> None:
    h = make_model({"FrameObj.SetOutputStations": 0})
    with pytest.raises(ValueError, match="exactly one"):
        h.model.frames.set_output_stations("F1")
    with pytest.raises(ValueError, match="exactly one"):
        h.model.frames.set_output_stations("F1", min_stations=3, max_segment_size=1.0)


def test_output_stations_min_count(make_model) -> None:
    h = make_model({"FrameObj.SetOutputStations": 0})
    h.model.frames.set_output_stations("F1", min_stations=5)
    (args,) = h.called("FrameObj.SetOutputStations")
    # (name, myType=2, maxSeg=0.0, minSections=5, noOut, noOut, itemType)
    assert args == ("F1", 2, 0.0, 5, False, False, 0)


def test_output_stations_max_segment(make_model) -> None:
    h = make_model({"FrameObj.SetOutputStations": 0})
    h.model.frames.set_output_stations("F1", max_segment_size=0.5)
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
    h.model.frames.add_to_group("F1", g)
    assert h.called("GroupDef.SetGroup") == [("piers",)]
    assert h.called("FrameObj.SetGroupAssign") == [("F1", "piers", False, 0)]
