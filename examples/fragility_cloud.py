"""Fit a cloud fragility curve from a synthetic mini-suite.

Run the SAP-backed demand collection with a local SAP2000 install::

    uv run python examples/fragility_cloud.py --sap
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from sap2000py import RayleighDamping, SapClient, Units
from sap2000py.bridge import ContinuousGirderBridge
from sap2000py.fiber import MomentCurvature
from sap2000py.seismic import (
    NlthConfig,
    bridge_edps,
    cloud_fragility,
    demands,
    fit_psdm,
    read_suite,
    run_nlth_batch,
)
from sap2000py.seismic.hinges import DamageStates, damage_states_from_mc

MOTIONS = Path(__file__).parent / "seismic_bridge" / "motions"


def _demo_damage_states() -> DamageStates:
    # ponytail: a tiny synthetic MC object is enough to demonstrate DS extraction.
    mc = MomentCurvature(
        curvature=np.asarray([0.0, 0.001, 0.002, 0.004, 0.006]),
        moment=np.asarray([0.0, 1000.0, 1700.0, 2100.0, 2200.0]),
        axial=0.0,
    )
    return damage_states_from_mc(mc, mu=(1.0, 1.6, 2.4, 3.2))


def _require_sap() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sap", action="store_true", help="run against a local SAP2000 install")
    if not parser.parse_args().sap:
        raise SystemExit("Pass --sap to run this example against SAP2000.")


def main() -> None:
    _require_sap()
    suite = read_suite(MOTIONS, pattern="synth_*.csv")
    damage = _demo_damage_states()

    with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
        m = client.model
        m.files.new_blank(units=Units.KN_M_C)
        m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
        m.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
        m.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)
        build = ContinuousGirderBridge(
            "fragility_bridge",
            spans=[35, 35],
            pier_height=10.0,
            girder_section="Girder",
            pier_section="Pier",
            bearing_stiffness=[1.0e9, 1.0e9, 2.0e10, 0.0, 0.0, 0.0],
            pier_segments=3,
        ).build(m)
        m.loads.set_mass_source(from_elements=True, from_masses=True)
        m.loads.cases.add_static_linear("GRAV", loads={"DEAD": 1.0})
        m.files.save(Path(__file__).with_name("fragility_cloud.sdb"))

        results = run_nlth_batch(
            m,
            suite,
            edps=bridge_edps(build, dof="U1")[:1],
            config=NlthConfig(
                damping=RayleighDamping.from_periods(0.3, 1.5, 0.05),
                gravity_case="GRAV",
            ),
            ims=("pga",),
            scale={
                "synth_01": 0.8,
                "synth_02": 1.0,
                "synth_03": 1.2,
                "synth_04": 1.4,
                "synth_05": 1.6,
            },
            workdir=Path(__file__).with_name("fragility_work"),
        )

    edp_name = next(iter(results[0].edp))
    im, edp = demands(results, edp=edp_name, im="pga")
    psdm = fit_psdm(im, edp)
    capacity = next(iter(damage.thresholds.values()))
    curve = cloud_fragility(psdm, capacity, beta_capacity=0.25, label="slight")
    print(f"theta={curve.theta:.4f}g  beta={curve.beta:.4f}")


if __name__ == "__main__":
    main()
