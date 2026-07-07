"""Unit tests for bridge seismic isolator components."""

from __future__ import annotations

from typing import Any

from sap2000py.bridge import (
    ContinuousGirderBridge,
    FrictionPendulumBearing,
    LeadRubberBearing,
)


def isolator_responses() -> dict[str, Any]:
    return {
        "PointObj.AddCartesian": lambda *a: [a[4] or "P", 0],
        "PointObj.SetRestraint": 0,
        "PropFrame.GetNameList": (2, ("P", "G"), 0),
        "FrameObj.AddByPoint": lambda *a: [a[4] or "F", 0],
        "LinkObj.AddByPoint": lambda *a: [a[5] or "L", 0],
        "PropLink.SetLinear": 0,
        "PropLink.SetPlasticWen": 0,
        "PropLink.SetFrictionIsolator": 0,
        "ConstraintDef.SetBody": 0,
        "PointObj.SetConstraint": 0,
    }


def test_lead_rubber_bearing_builds_plastic_wen_link(make_model) -> None:
    h = make_model(isolator_responses())
    b = LeadRubberBearing(
        "LRB",
        1.0,
        2.0,
        3.0,
        vertical_stiffness=1000.0,
        shear_stiffness=50.0,
        yield_force=8.0,
        post_yield_ratio=0.12,
        height=0.4,
    )

    b.build(h.model)

    assert h.called("PropLink.SetPlasticWen")[0] == (
        "LRB_prop",
        [True, True, True, False, False, False],
        [False] * 6,
        [False, True, True, False, False, False],
        [1000.0, 50.0, 50.0, 0.0, 0.0, 0.0],
        [0.0] * 6,
        [0.0, 50.0, 50.0, 0.0, 0.0, 0.0],
        [0.0, 8.0, 8.0, 0.0, 0.0, 0.0],
        [0.0, 0.12, 0.12, 0.0, 0.0, 0.0],
        [0.0, 2.0, 2.0, 0.0, 0.0, 0.0],
        0.0,
        0.0,
        "",
    )
    assert h.called("LinkObj.AddByPoint")[0] == ("LRB_b", "LRB_t", "", False, "LRB_prop", "LRB")
    assert b.anchor("bottom").name == "LRB_b"
    assert b.anchor("top").name == "LRB_t"


def test_friction_pendulum_bearing_builds_friction_isolator_link(make_model) -> None:
    h = make_model(isolator_responses())
    b = FrictionPendulumBearing(
        "FPS",
        0.0,
        0.0,
        5.0,
        vertical_stiffness=2000.0,
        initial_stiffness=80.0,
        friction_slow=0.03,
        friction_fast=0.05,
        rate=2.0,
        radius=3.0,
    )

    b.build(h.model)

    call = h.called("PropLink.SetFrictionIsolator")[0]
    assert call[:6] == (
        "FPS_prop",
        [True, True, True, False, False, False],
        [False] * 6,
        [False, True, True, False, False, False],
        [2000.0, 80.0, 80.0, 0.0, 0.0, 0.0],
        [0.0] * 6,
    )
    assert call[6:11] == (
        [0.0, 80.0, 80.0, 0.0, 0.0, 0.0],
        [0.0, 0.03, 0.03, 0.0, 0.0, 0.0],
        [0.0, 0.05, 0.05, 0.0, 0.0, 0.0],
        [0.0, 2.0, 2.0, 0.0, 0.0, 0.0],
        [0.0, 3.0, 3.0, 0.0, 0.0, 0.0],
    )
    assert h.called("LinkObj.AddByPoint")[0] == ("FPS_b", "FPS_t", "", False, "FPS_prop", "FPS")


def test_continuous_bridge_default_bearing_maker_regression(make_model) -> None:
    h = make_model(isolator_responses())
    b = ContinuousGirderBridge(
        "B",
        spans=[40, 40],
        pier_height=10.0,
        girder_section="G",
        pier_section="P",
        bearing_stiffness=[2e5, 2e5, 2e9, 0, 0, 0],
    )

    b.build(h.model)

    assert len(h.called("LinkObj.AddByPoint")) == 3
    assert len(h.called("PropLink.SetLinear")) == 3
    assert h.called("PropLink.SetPlasticWen") == []
    assert h.called("PropLink.SetFrictionIsolator") == []
    assert h.called("LinkObj.AddByPoint")[0] == (
        "B_B0_b",
        "B_B0_t",
        "",
        False,
        "B_B0_prop",
        "B_B0",
    )
