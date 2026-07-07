"""Unit tests for nonlinear time-history runners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sap2000py import Units
from sap2000py.model import RayleighDamping
from sap2000py.seismic import GroundMotionRecord, GroundMotionSuite
from sap2000py.seismic.edp import PierDrift
from sap2000py.seismic.runner import NlthConfig, run_nlth_batch


def runner_responses(*, status: int = 4) -> dict[str, Any]:
    selected: dict[str, str] = {"case": ""}

    def select_case(case: str, selected_flag: bool) -> int:
        if selected_flag:
            selected["case"] = case
        return 0

    def joint_displ(name: str, _item_type: int) -> tuple[Any, ...]:
        values = {
            "top": (0.0, 0.2),
            "bottom": (0.0, -0.1),
        }[name]
        case = selected["case"]
        return (
            2,
            (name, name),
            ("", ""),
            (case, case),
            ("Step", "Step"),
            (0.0, 1.0),
            values,
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
            (0.0, 0.0),
            0,
        )

    return {
        "SetModelIsLocked": 0,
        "LoadCases.Delete": 1,
        "Func.Delete": 1,
        "Func.FuncTH.SetUser": 0,
        "GetPresentUnits": int(Units.KN_M_C),
        "LoadCases.DirHistNonLinear.SetCase": 0,
        "LoadCases.DirHistNonLinear.SetTimeIntegration": 0,
        "LoadCases.DirHistNonLinear.SetDampProportional": 0,
        "LoadCases.DirHistNonLinear.SetGeometricNonLinearity": 0,
        "LoadCases.DirHistNonLinear.SetTimeStep": 0,
        "LoadCases.DirHistNonLinear.SetLoads": 0,
        "Results.Setup.SetOptionDirectHist": 0,
        "GetModelFilename": "model.sdb",
        "Analyze.SetRunCaseFlag": 0,
        "Analyze.RunAnalysis": 0,
        "Analyze.GetCaseStatus": (1, ("__nlth_r1", "__nlth_r2"), (status, status), 0),
        "Results.Setup.DeselectAllCasesAndCombosForOutput": 0,
        "Results.Setup.SetCaseSelectedForOutput": select_case,
        "Results.JointDispl": joint_displ,
    }


def suite() -> GroundMotionSuite:
    return GroundMotionSuite(
        (
            GroundMotionRecord("r1", 0.02, np.asarray([0.0, 0.1])),
            GroundMotionRecord("r2", 0.02, np.asarray([0.0, 0.2])),
        )
    )


def config() -> NlthConfig:
    return NlthConfig(damping=RayleighDamping.from_coefficients(0.0, 0.0))


def test_run_nlth_batch_extracts_before_next_unlock(make_model, tmp_path: Path) -> None:
    h = make_model(runner_responses())
    edps = [PierDrift("drift", top="top", bottom="bottom", height=10.0)]
    results = run_nlth_batch(
        h.model,
        suite(),
        edps=edps,
        config=config(),
        workdir=tmp_path,
    )
    assert [result.finished for result in results] == [True, True]
    assert results[0].edp["drift"] == pytest.approx(0.03)
    unlocks = [i for i, call in enumerate(h.calls) if call == ("SetModelIsLocked", (False,))]
    result_reads = [i for i, (name, _args) in enumerate(h.calls) if name == "Results.JointDispl"]
    assert result_reads[0] < unlocks[1]
    assert (tmp_path / "r1.json").exists()
    assert (tmp_path / "r2.json").exists()
    assert (tmp_path / "results.jsonl").exists()


def test_run_nlth_batch_resume_skips_checkpointed_record(make_model, tmp_path: Path) -> None:
    checkpoint = {
        "record": "r1",
        "case": "__nlth_r1",
        "scale": 1.0,
        "im": {"pga": 0.1},
        "edp": {"drift": 0.02},
        "finished": True,
        "error": None,
    }
    (tmp_path / "r1.json").write_text(json.dumps(checkpoint), encoding="utf-8")
    h = make_model({})
    results = run_nlth_batch(
        h.model,
        GroundMotionSuite((GroundMotionRecord("r1", 0.02, np.asarray([0.0, 0.1])),)),
        edps=[],
        config=config(),
        workdir=tmp_path,
    )
    assert results[0].edp["drift"] == 0.02
    assert h.calls == []


def test_run_nlth_batch_on_error_skip_returns_failed_result(make_model, tmp_path: Path) -> None:
    h = make_model(runner_responses(status=3))
    result = run_nlth_batch(
        h.model,
        GroundMotionSuite((GroundMotionRecord("r1", 0.02, np.asarray([0.0, 0.1])),)),
        edps=[],
        config=config(),
        workdir=tmp_path,
        on_error="skip",
    )[0]
    assert result.finished is False
    assert result.error is not None


def test_run_nlth_batch_accepts_callable_intensity_measure(make_model, tmp_path: Path) -> None:
    h = make_model(runner_responses())

    def custom_im(record: GroundMotionRecord) -> float:
        return record.pga + 2.0

    result = run_nlth_batch(
        h.model,
        GroundMotionSuite((GroundMotionRecord("r1", 0.02, np.asarray([0.0, 0.1])),)),
        edps=[],
        config=config(),
        ims=(custom_im,),
        workdir=tmp_path,
    )[0]
    assert result.im == {"custom_im": pytest.approx(2.1)}


def test_run_nlth_batch_rejects_bare_sa_avg_string(make_model, tmp_path: Path) -> None:
    h = make_model({})
    with pytest.raises(ValueError, match="IM 'sa_avg' requires a periods band"):
        run_nlth_batch(
            h.model,
            GroundMotionSuite((GroundMotionRecord("r1", 0.02, np.asarray([0.0, 0.1])),)),
            edps=[],
            config=config(),
            ims=("sa_avg",),
            workdir=tmp_path,
        )
    assert h.calls == []
