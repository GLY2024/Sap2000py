"""Run a response-spectrum check on a small continuous bridge.

Run with a local SAP2000 install and the ``bridge`` extra::

    uv run python examples/seismic_bridge/response_spectrum.py --sap
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sap2000py import SapClient, SpectrumLoad, Units
from sap2000py.bridge import ContinuousGirderBridge
from sap2000py.seismic import jtg2231_spectrum


def _require_sap() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sap", action="store_true", help="run against a local SAP2000 install")
    if not parser.parse_args().sap:
        raise SystemExit("Pass --sap to run this example against SAP2000.")


def main() -> None:
    _require_sap()
    with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
        m = client.model
        m.files.new_blank(units=Units.KN_M_C)
        m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
        m.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
        m.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)
        m.loads.set_mass_source(from_elements=True, from_masses=True)

        bridge = ContinuousGirderBridge(
            "rs_bridge",
            spans=[35, 35],
            pier_height=10.0,
            girder_section="Girder",
            pier_section="Pier",
            bearing_stiffness=[1.0e9, 1.0e9, 2.0e10, 0.0, 0.0, 0.0],
            pier_segments=3,
        )
        build = bridge.build(m)

        design = jtg2231_spectrum(peak_accel=0.2, tg=0.45, t_max=4.0, dt=0.02)
        m.functions.rs.add_user("JTG2231_E2", design.periods, design.values, damping=design.damping)
        m.functions.rs.add_jtg_b02_2013(
            "JTG_B02_E1",
            direction=1,
            peak_accel=0.1,
            tg=0.35,
            ci=1.0,
            cs=1.0,
        )
        m.loads.cases.add_modal_eigen("MODAL", num_modes=12)
        m.loads.cases.add_response_spectrum(
            "RS_U1",
            loads=[SpectrumLoad("U1", "JTG2231_E2", scale=1.0)],
            modal_case="MODAL",
        )

        m.files.save(Path(__file__).with_name("response_spectrum.sdb"))
        m.analysis.run(cases=["MODAL", "RS_U1"])
        m.results.select_output(cases=["RS_U1"])

        print("Base reactions")
        for row in m.results.base_reactions().rows():
            print(f"{row['case']:>8}  FX={row['FX']:>10.3f}  FY={row['FY']:>10.3f}")

        pier_frame = f"{build.piers[1].name}_e0"
        print("\nPier forces")
        for row in m.results.frame_forces(pier_frame).rows():
            print(f"{row['frame']:>16}  P={row['P']:>10.3f}  M3={row['M3']:>10.3f}")


if __name__ == "__main__":
    main()
