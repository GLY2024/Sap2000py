"""Unit tests for seismic EDP extractors."""

from __future__ import annotations

import pytest

from sap2000py.bridge import ContinuousGirderBridge
from sap2000py.seismic.edp import BearingDeformation, PierDrift, bridge_edps

from .test_bridge import bridge_responses


def result_responses() -> dict[str, object]:
    def joint_displ(name: str, _item_type: int) -> tuple[object, ...]:
        values = {
            "top": (0.0, 0.10, -0.20),
            "bottom": (0.0, -0.05, 0.05),
        }[name]
        return (
            3,
            (name, name, name),
            ("", "", ""),
            ("case1", "case1", "case1"),
            ("Step", "Step", "Step"),
            (0.0, 1.0, 2.0),
            values,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            0,
        )

    def link_deformation(name: str, _item_type: int) -> tuple[object, ...]:
        return (
            3,
            (name, name, name),
            ("", "", ""),
            ("case1", "case1", "case1"),
            ("Step", "Step", "Step"),
            (0.0, 1.0, 2.0),
            (0.01, -0.04, 0.03),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            0,
        )

    return {
        "Results.JointDispl": joint_displ,
        "Results.LinkDeformation": link_deformation,
    }


def test_pier_drift_uses_peak_relative_step_displacement(make_model) -> None:
    h = make_model(result_responses())
    edp = PierDrift("drift", top="top", bottom="bottom", height=10.0)
    assert edp.extract(h.model, "case1") == pytest.approx(0.025)


def test_bearing_deformation_uses_peak_abs_link_deformation(make_model) -> None:
    h = make_model(result_responses())
    edp = BearingDeformation("bearing", link="L1")
    assert edp.extract(h.model, "case1") == pytest.approx(0.04)


def test_bridge_edps_walks_bridge_build(make_model) -> None:
    h = make_model(bridge_responses())
    bridge = ContinuousGirderBridge(
        "B",
        spans=[20.0],
        pier_height=5.0,
        girder_section="G",
        pier_section="P",
        bearing_stiffness=[1.0] * 6,
    )
    build = bridge.build(h.model)
    edps = bridge_edps(build)
    assert [edp.name for edp in edps] == [
        "B_P0_drift_U1",
        "B_P1_drift_U1",
        "B_B0_deformation_U1",
        "B_B1_deformation_U1",
    ]
