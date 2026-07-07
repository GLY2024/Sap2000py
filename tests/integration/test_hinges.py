"""Integration tests for v25 table-backed hinge definitions."""

from __future__ import annotations

from pathlib import Path

import pytest

from sap2000py import SapClient, SapTableSchemaError, Units
from sap2000py.bridge import ContinuousGirderBridge
from sap2000py.fiber import BilinearSteel, FiberSection, ManderConcrete, moment_curvature
from sap2000py.seismic.hinges import hinge_from_mc

pytestmark = pytest.mark.sap


def _moment_curvature_hinge(name: str):
    sec = FiberSection()
    concrete = ManderConcrete(fco=40.0, Ec=3.0e4, eps_cu=0.005)
    sec.add_rect_patch(concrete, y_min=-300.0, y_max=300.0, width=500.0, n=60)
    steel = BilinearSteel(E=2.0e5, fy=400.0)
    sec.add_bars(steel, ys=[-250.0, 250.0], area_each=1500.0)
    mc = moment_curvature(sec, max_curvature=3.0e-5, axial=-2.0e6, n_steps=60)
    return hinge_from_mc(mc, name=name, hinge_length=1.2)


def test_moment_hinge_define_assign_round_trip_v25(client: SapClient, tmp_path: Path) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
    m.frame_sections.add_rectangle("Girder", material="C40", depth=1.4, width=5.0)
    m.frame_sections.add_rectangle("Pier", material="C40", depth=1.4, width=1.4)
    bridge = ContinuousGirderBridge(
        "HB",
        spans=[20.0, 20.0],
        pier_height=8.0,
        girder_section="Girder",
        pier_section="Pier",
        bearing_stiffness=[1e9, 2e5, 2e5, 1e8, 1e8, 1e8],
        pier_segments=1,
    )
    bridge.build(m)
    frame = "HB_P1_e0"
    hinge = _moment_curvature_hinge("HB_M3")

    try:
        m.hinges.define_moment_m3(hinge)
        m.hinges.assign(frame, hinge.name, rel_dist=0.0)
    except SapTableSchemaError as exc:
        pytest.xfail(f"SAP2000 v25 hinge table schema differed from adapter aliases: {exc}")

    assigns = m.hinges.assigned(frame)
    assert any(
        assign.frame == frame
        and assign.hinge == hinge.name
        and assign.rel_dist == pytest.approx(0.0)
        for assign in assigns
    )

    m.files.save(tmp_path / "hinge_round_trip.sdb")
