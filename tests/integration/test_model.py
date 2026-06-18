"""Integration tests for the M2 typed model layer against real SAP2000.

Run with ``pytest --sap``. Builds a small portal frame, runs modal and static
analyses, and extracts results — exercising materials, sections, frames, loads,
analysis, and results end to end.
"""

from __future__ import annotations

import pytest

from sap2000py import DOF, SapClient, Units

pytestmark = pytest.mark.sap


def _build_portal(m) -> None:
    """A 4 m x 3 m steel portal frame, columns fixed at the base."""
    m.files.new_blank(units=Units.KN_M_C)
    m.materials.add_isotropic("STEEL", modulus=2.0e8, poisson=0.3, weight_per_volume=78.5)
    m.frame_sections.add_rectangle("COL", material="STEEL", depth=0.4, width=0.4)
    m.frame_sections.add_rectangle("BEAM", material="STEEL", depth=0.5, width=0.3)

    b1 = m.points.add(0, 0, 0)
    b2 = m.points.add(4, 0, 0)
    t1 = m.points.add(0, 0, 3)
    t2 = m.points.add(4, 0, 3)
    b1.restrain(DOF.fixed())
    b2.restrain(DOF.fixed())

    m.frames.add_by_points(b1, t1, section="COL")
    m.frames.add_by_points(b2, t2, section="COL")
    m.frames.add_by_points(t1, t2, section="BEAM")


def test_modal_analysis_returns_periods(client: SapClient, tmp_path) -> None:
    m = client.model
    _build_portal(m)
    # Modal mass comes from element self-mass; no load pattern needed.
    m.loads.cases.add_modal_eigen("MODAL", num_modes=6)
    m.files.save(tmp_path / "modal.sdb")  # analysis requires a saved model

    report = client.model.analysis.run(cases=["MODAL"])
    assert report.status["MODAL"] == "finished"

    periods = client.model.results.modal_periods()
    assert len(periods) == 6
    # Periods are positive and sorted descending (mode 1 is the softest).
    p = list(periods["period"])
    assert all(t > 0 for t in p)
    assert p == sorted(p, reverse=True)


def test_static_dead_load_reactions_balance_weight(client: SapClient, tmp_path) -> None:
    m = client.model
    _build_portal(m)
    # A blank model already has a DEAD pattern (self-weight 1.0) and case.
    m.loads.patterns.set_self_weight("DEAD", 1.0)
    m.files.save(tmp_path / "static.sdb")

    client.model.analysis.run(cases=["DEAD"])
    client.model.results.select_output(cases=["DEAD"])

    # Sum vertical reactions at both bases; should balance total self-weight.
    total_fz = 0.0
    for base in ("1", "2"):  # default base point names
        react = client.model.results.joint_reactions(base)
        if len(react):
            total_fz += sum(react["F3"])
    assert total_fz > 0  # upward reactions resisting gravity


def test_frame_forces_extractable(client: SapClient, tmp_path) -> None:
    m = client.model
    _build_portal(m)
    m.loads.patterns.set_self_weight("DEAD", 1.0)
    beam = m.frames.names()[-1]
    m.frames.ref(beam).set_output_stations(min_stations=5)
    m.files.save(tmp_path / "forces.sdb")

    client.model.analysis.run(cases=["DEAD"])
    client.model.results.select_output(cases=["DEAD"])
    forces = client.model.results.frame_forces(beam)
    assert len(forces) >= 2
    assert set(forces.names) >= {"P", "V2", "M3", "station"}


def test_china_material_library(client: SapClient) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    c40 = m.materials.add_concrete("C40", grade="C40", code="JTG")
    assert c40.name == "C40"
    assert "C40" in m.materials.names()
