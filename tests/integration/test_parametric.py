"""Integration tests for the SAP-backed parametric-study driver."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from sap2000py import SapClient, Units
from sap2000py.bridge import ContinuousGirderBridge
from sap2000py.model import Model
from sap2000py.optimize import ParameterGrid, run_study

pytestmark = pytest.mark.sap


def _build_bridge_case(params: Mapping[str, Any], model: Model) -> None:
    height = float(params["pier_height"])
    model.set_units(Units.KN_M_C)
    model.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
    model.frame_sections.add_rectangle("Girder", material="C40", depth=1.4, width=5.0)
    model.frame_sections.add_rectangle("Pier", material="C40", depth=1.2, width=1.2)
    bridge = ContinuousGirderBridge(
        "PB",
        spans=[24.0, 24.0],
        pier_height=height,
        girder_section="Girder",
        pier_section="Pier",
        bearing_stiffness=[1e9, 2e5, 2e5, 1e8, 1e8, 1e8],
        pier_segments=1,
    )
    bridge.build(model)
    model.loads.cases.add_modal_eigen("MODAL", num_modes=3)


def _collect_period(_params: Mapping[str, Any], model: Model) -> dict[str, float]:
    periods = model.results.modal_periods()
    return {"period": float(periods["period"][0])}


def test_run_study_collects_modal_periods(client: SapClient, tmp_path: Path) -> None:
    table = run_study(
        client,
        ParameterGrid({"pier_height": [8.0, 12.0]}),
        build=_build_bridge_case,
        collect=_collect_period,
        workdir=tmp_path / "study",
        run_cases=["MODAL"],
        resume=False,
        units=Units.KN_M_C,
    )

    assert len(table) == 2
    assert set(table.names) >= {"pier_height", "period"}
    assert list(table["pier_height"]) == [8.0, 12.0]
    assert all(float(period) > 0.0 for period in table["period"])
