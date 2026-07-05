"""Integration tests for the M4 bridge layer against real SAP2000.

Run with ``pytest --sap``. These validate the OAPI signatures the bridge layer
relies on (``PointObj.SetSpring`` / ``SetConstraint``, ``ConstraintDef.SetBody`` /
``SetEqual``, ``PropLink.SetLinear``, ``LinkObj.AddByPoint``) end to end by
assembling a continuous girder bridge and running a modal analysis on it.
"""

from __future__ import annotations

import pytest

from sap2000py import SapClient, Units
from sap2000py.bridge import (
    Connection,
    ContinuousGirderBridge,
    Foundation,
    Pier,
    snap_connect,
)

pytestmark = pytest.mark.sap


def _define_sections(m) -> None:
    """A C40 concrete deck and pier section in a blank model."""
    m.files.new_blank(units=Units.KN_M_C)
    m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
    m.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
    m.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)


def test_build_continuous_bridge_and_run_modal(client: SapClient, tmp_path) -> None:
    m = client.model
    _define_sections(m)
    bridge = ContinuousGirderBridge(
        "B",
        spans=[40.0, 40.0],
        pier_height=12.0,
        girder_section="Girder",
        pier_section="Pier",
        # All-DOF stiff bearing keeps the modal model free of mechanisms.
        bearing_stiffness=[1.0e9, 1.0e9, 1.0e9, 1.0e8, 1.0e8, 1.0e8],
        pier_segments=2,
    )
    result = bridge.build(m)

    assert len(result.piers) == 3  # 2 spans -> 3 supports
    assert len(result.connections) == 9
    assert m.links.count() == 3  # one bearing link per support

    m.loads.cases.add_modal_eigen("MODAL", num_modes=6)
    m.files.save(tmp_path / "bridge.sdb")  # analysis requires a saved model

    report = m.analysis.run(cases=["MODAL"])
    assert report.status["MODAL"] == "finished"

    periods = m.results.modal_periods()
    assert len(periods) == 6
    assert all(t > 0 for t in periods["period"])


def test_spring_foundation_and_equal_constraint(client: SapClient) -> None:
    m = client.model
    _define_sections(m)
    foundation = Foundation(
        "FS", 0.0, 0.0, 0.0, kind="spring", stiffness=[1e6, 1e6, 1e6, 1e7, 1e7, 1e7]
    )
    pier = Pier("PS", (0.0, 0.0, 0.0), 10.0, "Pier")
    foundation.build(m)
    pier.build(m)

    name = snap_connect(m, foundation.anchor("top"), pier.anchor("bottom"), how=Connection.EQUAL)
    assert name in m.constraints.names()
