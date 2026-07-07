"""Unit tests for the parametric-study driver."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from sap2000py import SapClient, Units
from sap2000py.model import Model
from sap2000py.optimize import ParameterGrid, run_study


def test_parameter_grid_cartesian_product_preserves_axis_order() -> None:
    grid = ParameterGrid({"height": [8.0, 12.0], "bearing": ["linear", "lrb"]})

    assert len(grid) == 4
    assert list(grid.combos()) == [
        {"height": 8.0, "bearing": "linear"},
        {"height": 8.0, "bearing": "lrb"},
        {"height": 12.0, "bearing": "linear"},
        {"height": 12.0, "bearing": "lrb"},
    ]


def test_run_study_checkpoints_and_resumes(make_model, tmp_path: Path) -> None:
    h = make_model(
        {
            "InitializeNewModel": 0,
            "File.NewBlank": 0,
            "File.Save": 0,
            "GetModelFilename": "study.sdb",
            "Analyze.SetRunCaseFlag": 0,
            "Analyze.RunAnalysis": 0,
            "Analyze.GetCaseStatus": (1, ("MODAL",), (4,), 0),
        }
    )
    client = cast(SapClient, SimpleNamespace(model=h.model))
    built: list[dict[str, object]] = []

    def build(params: dict[str, object], model: Model) -> None:
        assert model is h.model
        built.append(dict(params))

    def collect(params: dict[str, object], model: Model) -> dict[str, float]:
        assert model is h.model
        return {"period": float(params["height"]) / 10.0}

    grid = ParameterGrid({"height": [8.0, 12.0]})
    table = run_study(
        client,
        grid,
        build=build,
        collect=collect,
        workdir=tmp_path,
        run_cases=["MODAL"],
        units=Units.KN_M_C,
    )

    assert table.rows() == [
        {"height": 8.0, "period": 0.8},
        {"height": 12.0, "period": 1.2},
    ]
    assert table.names == ["height", "period"]
    assert built == [{"height": 8.0}, {"height": 12.0}]
    assert h.called("InitializeNewModel") == [(int(Units.KN_M_C),), (int(Units.KN_M_C),)]
    assert len(h.called("File.NewBlank")) == 2
    saved = [Path(call[0]) for call in h.called("File.Save")]
    assert all(path.parent == tmp_path for path in saved)
    assert all(path.name.startswith("case_") and path.suffix == ".sdb" for path in saved)
    assert saved[0].name != saved[1].name
    assert ("MODAL", True, False) in h.called("Analyze.SetRunCaseFlag")

    lines = (tmp_path / "study.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["row"]["period"] for line in lines] == [0.8, 1.2]

    resumed = run_study(
        cast(SapClient, SimpleNamespace(model=make_model({}).model)),
        grid,
        build=build,
        collect=collect,
        workdir=tmp_path,
        run_cases=["MODAL"],
    )

    assert resumed.rows() == table.rows()
    assert resumed.names == ["height", "period"]
    assert built == [{"height": 8.0}, {"height": 12.0}]
