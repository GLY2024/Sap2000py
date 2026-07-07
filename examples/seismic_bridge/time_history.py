"""Run a short direct-integration NLTH bridge example.

Run with a local SAP2000 install and the ``bridge`` extra::

    uv run python examples/seismic_bridge/time_history.py --sap
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sap2000py import RayleighDamping, SapClient, Units
from sap2000py.bridge import ContinuousGirderBridge
from sap2000py.seismic import NlthConfig, bridge_edps, read_suite, run_nlth_batch

CONFIG = Path(__file__).parents[1] / "continuous_bridge" / "bridge.yaml"
MOTIONS = Path(__file__).with_name("motions")


def _require_sap() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sap", action="store_true", help="run against a local SAP2000 install")
    if not parser.parse_args().sap:
        raise SystemExit("Pass --sap to run this example against SAP2000.")


def main() -> None:
    _require_sap()
    suite = read_suite(MOTIONS, pattern="synth_0[1-2].csv")
    with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
        m = client.model
        m.files.new_blank(units=Units.KN_M_C)
        m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
        m.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
        m.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)
        build = ContinuousGirderBridge.from_yaml(CONFIG).build(m)
        m.loads.set_mass_source(from_elements=True, from_masses=True)
        m.loads.cases.add_static_linear("GRAV", loads={"DEAD": 1.0})
        m.files.save(Path(__file__).with_name("time_history.sdb"))

        results = run_nlth_batch(
            m,
            suite,
            edps=bridge_edps(build, dof="U1"),
            config=NlthConfig(
                damping=RayleighDamping.from_periods(0.3, 1.5, 0.05),
                gravity_case="GRAV",
            ),
            ims=("pga",),
            workdir=Path(__file__).with_name("nlth_work"),
        )

        print("Record  PGA(g)  first EDP")
        for result in results:
            first_edp = next(iter(result.edp.values()), float("nan"))
            print(f"{result.record:>6}  {result.im.get('pga', 0.0):>6.3f}  {first_edp:>9.5f}")


if __name__ == "__main__":
    main()
