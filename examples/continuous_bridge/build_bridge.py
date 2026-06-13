"""Assemble a continuous girder bridge from a YAML config and run modal analysis.

Run with a local SAP2000 install and the ``bridge`` extra::

    uv run python examples/continuous_bridge/build_bridge.py

Demonstrates the M4 bridge layer: define the sections, load the bridge spec from
``bridge.yaml`` (resolved relative to this file, so there are no hard-coded
paths), build + auto-connect every component, then analyze.
"""

from __future__ import annotations

from pathlib import Path

from sap2000py import SapClient, Units
from sap2000py.bridge import ContinuousGirderBridge

CONFIG = Path(__file__).with_name("bridge.yaml")


def main() -> None:
    with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
        m = client.model
        m.files.new_blank(units=Units.KN_M_C)

        # The assembler owns geometry/topology; sections are defined here.
        m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
        m.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
        m.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)

        bridge = ContinuousGirderBridge.from_yaml(CONFIG)
        result = bridge.build(m)
        print(
            f"Built {len(result.piers)} supports, "
            f"{len(result.bearings)} bearings, "
            f"{len(result.connections)} connections."
        )

        m.loads.cases.add_modal_eigen("MODAL", num_modes=12)
        m.files.save(Path(__file__).with_name("continuous_bridge.sdb"))
        m.analysis.run(cases=["MODAL"])

        periods = m.results.modal_periods()
        print("Mode  Period (s)")
        for row in periods.rows():
            print(f"{row['mode']:>4}  {row['period']:>10.4f}")


if __name__ == "__main__":
    main()
