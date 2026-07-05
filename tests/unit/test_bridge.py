"""Unit tests for the M4 bridge component library (fake COM, no SAP2000)."""

from __future__ import annotations

from typing import Any

import pytest

from sap2000py.bridge import (
    Bearing,
    Connection,
    ContinuousGirderBridge,
    Foundation,
    Girder,
    Pier,
    bearing_preset,
    bearing_presets,
    snap_connect,
)


def bridge_responses() -> dict[str, Any]:
    """A fake COM surface covering every OAPI method the bridge layer calls.

    Name-returning [in,out] methods echo the requested UserName so anchors get
    meaningful names; status-only methods return 0 (success).
    """
    return {
        "PointObj.AddCartesian": lambda *a: [a[4] or "P", 0],
        "PointObj.GetNameList": (2, ("A", "B"), 0),
        "PointObj.SetRestraint": 0,
        "PointObj.SetSpring": 0,
        "PointObj.SetConstraint": 0,
        "PropFrame.GetNameList": (4, ("PierSec", "GirderSec", "P", "G"), 0),
        "FrameObj.AddByPoint": lambda *a: [a[4] or "F", 0],
        "LinkObj.AddByPoint": lambda *a: [a[5] or "L", 0],
        "PropLink.SetLinear": 0,
        "ConstraintDef.SetBody": 0,
        "ConstraintDef.SetEqual": 0,
    }


# -- components -------------------------------------------------------------


def test_foundation_fixed_restrains_base(make_model) -> None:
    h = make_model(bridge_responses())
    f = Foundation("F1", 0.0, 0.0, 0.0)
    f.build(h.model)
    assert len(h.called("PointObj.AddCartesian")) == 1
    assert len(h.called("PointObj.SetRestraint")) == 1
    assert f.anchor("top").name == "F1_base"


def test_foundation_spring_applies_stiffness(make_model) -> None:
    h = make_model(bridge_responses())
    f = Foundation("F1", 0.0, 0.0, 0.0, kind="spring", stiffness=[1e5] * 6)
    f.build(h.model)
    spring_calls = h.called("PointObj.SetSpring")
    assert len(spring_calls) == 1
    assert spring_calls[0][1] == [1e5] * 6  # stiffness array forwarded


def test_foundation_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        Foundation("F1", 0.0, 0.0, 0.0, kind="floating")


def test_foundation_spring_without_stiffness_rejected() -> None:
    with pytest.raises(ValueError, match="stiffness"):
        Foundation("F1", 0.0, 0.0, 0.0, kind="spring")


def test_foundation_fixed_uses_custom_dof_mask(make_model) -> None:
    h = make_model(bridge_responses())
    mask = [True, True, True, False, False, False]
    f = Foundation("F1", 0.0, 0.0, 0.0, fix_dof=mask)
    f.build(h.model)
    restraint_calls = h.called("PointObj.SetRestraint")
    assert len(restraint_calls) == 1
    assert restraint_calls[0][1] == mask


def test_pier_creates_segment_points_and_frames(make_model) -> None:
    h = make_model(bridge_responses())
    p = Pier("P1", (0.0, 0.0, 0.0), 10.0, "PierSec", segments=4)
    p.build(h.model)
    assert len(h.called("PointObj.AddCartesian")) == 5  # segments + 1
    assert len(h.called("FrameObj.AddByPoint")) == 4
    assert p.anchor("bottom").name == "P1_p0"
    assert p.anchor("top").name == "P1_p4"


def test_pier_rejects_base_that_is_not_xyz() -> None:
    with pytest.raises(ValueError, match="base"):
        Pier("P1", (0.0, 0.0), 10.0, "PierSec")


def test_pier_rejects_nonpositive_height() -> None:
    with pytest.raises(ValueError, match="height"):
        Pier("P1", (0.0, 0.0, 0.0), 0.0, "PierSec")


def test_pier_rejects_zero_segments() -> None:
    with pytest.raises(ValueError, match="segments"):
        Pier("P1", (0.0, 0.0, 0.0), 10.0, "PierSec", segments=0)


def test_bearing_builds_link_between_distinct_points(make_model) -> None:
    h = make_model(bridge_responses())
    b = Bearing("B1", 0.0, 0.0, 10.0, stiffness=[2e5, 2e5, 2e9, 0, 0, 0])
    b.build(h.model)
    adds = h.called("PointObj.AddCartesian")
    assert len(adds) == 2
    # Both joints created with merge off (MergeOff arg == True) so a zero-height
    # bearing stays two nodes.
    assert all(call[6] is True for call in adds)
    assert len(h.called("PropLink.SetLinear")) == 1
    assert len(h.called("LinkObj.AddByPoint")) == 1


def test_bearing_rejects_stiffness_with_wrong_length() -> None:
    with pytest.raises(ValueError, match="stiffness must have 6"):
        Bearing("B1", 0.0, 0.0, 10.0, stiffness=[1.0, 2.0])


def test_bearing_height_offsets_top_point(make_model) -> None:
    h = make_model(bridge_responses())
    b = Bearing("B1", 1.0, 2.0, 10.0, stiffness=[1.0] * 6, height=0.75)
    b.build(h.model)
    adds = h.called("PointObj.AddCartesian")
    assert adds[0][:5] == (1.0, 2.0, 10.0, "", "B1_b")
    assert adds[1][:5] == (1.0, 2.0, 10.75, "", "B1_t")


def test_girder_chains_nodes(make_model) -> None:
    h = make_model(bridge_responses())
    g = Girder("G", [(0, 0, 5), (10, 0, 5), (20, 0, 5)], "GirderSec")
    g.build(h.model)
    assert len(h.called("PointObj.AddCartesian")) == 3
    assert len(h.called("FrameObj.AddByPoint")) == 2
    assert g.anchor("start").name == "G_n0"
    assert g.anchor("end").name == "G_n2"


def test_girder_rejects_fewer_than_two_nodes() -> None:
    with pytest.raises(ValueError, match="at least 2 nodes"):
        Girder("G", [(0.0, 0.0, 5.0)], "GirderSec")


# -- component protocol -----------------------------------------------------


def test_anchor_before_build_raises() -> None:
    with pytest.raises(RuntimeError, match="not built"):
        Foundation("F1", 0.0, 0.0, 0.0).anchor("top")


def test_component_built_flag_changes_after_build(make_model) -> None:
    h = make_model(bridge_responses())
    f = Foundation("F1", 0.0, 0.0, 0.0)
    assert f.built is False
    f.build(h.model)
    assert f.built is True


def test_component_anchors_returns_defensive_copy(make_model) -> None:
    h = make_model(bridge_responses())
    f = Foundation("F1", 0.0, 0.0, 0.0)
    f.build(h.model)
    anchors = f.anchors
    assert anchors["top"].name == "F1_base"
    anchors.clear()
    assert f.anchor("top").name == "F1_base"


def test_build_twice_raises(make_model) -> None:
    h = make_model(bridge_responses())
    f = Foundation("F1", 0.0, 0.0, 0.0)
    f.build(h.model)
    with pytest.raises(RuntimeError, match="already built"):
        f.build(h.model)


def test_unknown_anchor_raises(make_model) -> None:
    h = make_model(bridge_responses())
    f = Foundation("F1", 0.0, 0.0, 0.0)
    f.build(h.model)
    with pytest.raises(KeyError, match="no anchor"):
        f.anchor("nope")


# -- snap_connect -----------------------------------------------------------


def test_snap_connect_body_defines_and_assigns(make_model) -> None:
    h = make_model(bridge_responses())
    name = snap_connect(h.model, "A", "B", how=Connection.BODY, name="J")
    assert name == "J"
    assert len(h.called("ConstraintDef.SetBody")) == 1
    assert len(h.called("PointObj.SetConstraint")) == 2


@pytest.mark.parametrize(
    ("how", "path"),
    [(Connection.BODY, "ConstraintDef.SetBody"), (Connection.EQUAL, "ConstraintDef.SetEqual")],
)
def test_snap_connect_forwards_explicit_dof_mask(make_model, how, path) -> None:
    h = make_model(bridge_responses())
    mask = [True, False, False, False, False, True]
    snap_connect(h.model, "A", "B", how=how, dof=mask, name="J")
    calls = h.called(path)
    assert len(calls) == 1
    assert calls[0][1] == mask


def test_snap_connect_uses_anchor_names_when_name_is_omitted(make_model) -> None:
    h = make_model(bridge_responses())
    name = snap_connect(h.model, "A", "B", how=Connection.BODY)
    assert name == "A~B"
    assert h.called("ConstraintDef.SetBody")[0][0] == "A~B"
    assert [call[1] for call in h.called("PointObj.SetConstraint")] == ["A~B", "A~B"]


def test_snap_connect_equal_uses_equal_constraint(make_model) -> None:
    h = make_model(bridge_responses())
    snap_connect(h.model, "A", "B", how="equal", name="J")
    assert len(h.called("ConstraintDef.SetEqual")) == 1
    assert len(h.called("PointObj.SetConstraint")) == 2


def test_snap_connect_rigid_link_builds_link(make_model) -> None:
    h = make_model(bridge_responses())
    snap_connect(h.model, "A", "B", how=Connection.RIGID_LINK, name="J")
    assert len(h.called("PropLink.SetLinear")) == 1
    assert len(h.called("LinkObj.AddByPoint")) == 1


# -- system assembler -------------------------------------------------------


def test_continuous_bridge_support_layout() -> None:
    b = ContinuousGirderBridge(
        "B",
        spans=[40, 50, 40],
        pier_height=12.0,
        girder_section="G",
        pier_section="P",
        bearing_stiffness=[1] * 6,
    )
    assert b.support_x == [0.0, 40.0, 90.0, 130.0]


def test_continuous_bridge_rejects_empty_spans() -> None:
    with pytest.raises(ValueError, match="at least one span"):
        ContinuousGirderBridge(
            "B",
            spans=[],
            pier_height=12.0,
            girder_section="G",
            pier_section="P",
            bearing_stiffness=[1] * 6,
        )


def test_continuous_bridge_rejects_nonpositive_span_length() -> None:
    with pytest.raises(ValueError, match="positive"):
        ContinuousGirderBridge(
            "B",
            spans=[40.0, 0.0],
            pier_height=12.0,
            girder_section="G",
            pier_section="P",
            bearing_stiffness=[1] * 6,
        )


def test_continuous_bridge_build_connects_every_interface(make_model) -> None:
    h = make_model(bridge_responses())
    b = ContinuousGirderBridge(
        "B",
        spans=[40, 40],
        pier_height=10.0,
        girder_section="G",
        pier_section="P",
        bearing_stiffness=[2e5, 2e5, 2e9, 0, 0, 0],
    )
    result = b.build(h.model)
    n_supports = 3  # 2 spans -> 3 supports
    assert len(result.foundations) == n_supports
    assert len(result.piers) == n_supports
    assert len(result.bearings) == n_supports
    # 3 interfaces per support: foundation-pier, pier-bearing, bearing-girder.
    assert len(result.connections) == 3 * n_supports
    assert len(h.called("ConstraintDef.SetBody")) == 3 * n_supports
    assert len(h.called("LinkObj.AddByPoint")) == n_supports  # one bearing each


def test_continuous_bridge_build_forwards_spring_foundations(make_model) -> None:
    h = make_model(bridge_responses())
    stiffness = [1e6, 2e6, 3e6, 4e6, 5e6, 6e6]
    b = ContinuousGirderBridge(
        "B",
        spans=[40],
        pier_height=10.0,
        girder_section="G",
        pier_section="P",
        bearing_stiffness=[2e5, 2e5, 2e9, 0, 0, 0],
        foundation="spring",
        foundation_stiffness=stiffness,
    )
    b.build(h.model)
    spring_calls = h.called("PointObj.SetSpring")
    assert len(spring_calls) == 2
    assert [call[1] for call in spring_calls] == [stiffness, stiffness]
    assert h.called("PointObj.SetRestraint") == []


def test_continuous_bridge_build_applies_origin_and_bearing_height(make_model) -> None:
    h = make_model(bridge_responses())
    b = ContinuousGirderBridge(
        "B",
        spans=[10.0, 15.0],
        pier_height=8.0,
        girder_section="G",
        pier_section="P",
        bearing_stiffness=[1.0] * 6,
        bearing_height=0.5,
        origin=(100.0, 5.0, 2.0),
    )
    result = b.build(h.model)
    points = {call[4]: call[:3] for call in h.called("PointObj.AddCartesian")}
    assert b.support_x == [100.0, 110.0, 125.0]
    assert result.girder.nodes == [
        (100.0, 5.0, 10.5),
        (110.0, 5.0, 10.5),
        (125.0, 5.0, 10.5),
    ]
    for i, x in enumerate([100.0, 110.0, 125.0]):
        assert points[f"B_F{i}_base"] == (x, 5.0, 2.0)
        assert points[f"B_P{i}_p0"] == (x, 5.0, 2.0)
        assert points[f"B_P{i}_p1"] == (x, 5.0, 10.0)
        assert points[f"B_B{i}_b"] == (x, 5.0, 10.0)
        assert points[f"B_B{i}_t"] == (x, 5.0, 10.5)
        assert points[f"B_girder_n{i}"] == (x, 5.0, 10.5)


def test_continuous_bridge_from_yaml(make_model, tmp_path) -> None:
    config = tmp_path / "span3.yaml"
    config.write_text(
        "spans: [30, 30]\n"
        "pier_height: 8.0\n"
        "girder_section: G\n"
        "pier_section: P\n"
        "bearing_stiffness: [1, 1, 1, 0, 0, 0]\n",
        encoding="utf-8",
    )
    bridge = ContinuousGirderBridge.from_yaml(config)
    assert bridge.name == "span3"  # defaulted from file stem
    assert bridge.support_x == [0.0, 30.0, 60.0]
    h = make_model(bridge_responses())
    result = bridge.build(h.model)
    assert len(result.connections) == 9  # 3 supports x 3 interfaces


# -- presets ----------------------------------------------------------------


def test_bearing_preset_returns_six_stiffnesses() -> None:
    ke = bearing_preset("pot_fixed")
    assert len(ke) == 6
    assert all(isinstance(k, float) for k in ke)


def test_bearing_preset_unknown_raises() -> None:
    with pytest.raises(KeyError, match="unknown bearing preset"):
        bearing_preset("does_not_exist")


def test_bearing_presets_lists_names() -> None:
    names = bearing_presets()
    assert "elastomeric_pad" in names
    assert "pot_fixed" in names
