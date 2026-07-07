"""Compare ductile and isolated bridge variants in a small parameter grid.

Run with a local SAP2000 install and the ``bridge`` extra::

    uv run python examples/parametric_study.py --sap
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sap2000py import LeadRubberBearing, SapClient, Units
from sap2000py.bridge import Bearing, BridgeComponent, ContinuousGirderBridge
from sap2000py.model import Model
from sap2000py.optimize import ParameterGrid, run_study


def _require_sap() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sap", action="store_true", help="run against a local SAP2000 install")
    if not parser.parse_args().sap:
        raise SystemExit("Pass --sap to run this example against SAP2000.")


def _bearing_maker(kind: str):
    def maker(name: str, x: float, y: float, z: float) -> BridgeComponent:
        if kind == "isolated":
            return LeadRubberBearing(
                name,
                x,
                y,
                z,
                vertical_stiffness=2.0e10,
                shear_stiffness=2.0e5,
                yield_force=350.0,
                post_yield_ratio=0.08,
            )
        return Bearing(name, x, y, z, stiffness=[1.0e9, 1.0e9, 2.0e10, 0.0, 0.0, 0.0])

    return maker


def _build(params: Mapping[str, Any], model: Model) -> None:
    model.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
    model.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
    model.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)
    bridge = ContinuousGirderBridge(
        "param_bridge",
        spans=[35, 35],
        pier_height=float(params["pier_height"]),
        girder_section="Girder",
        pier_section="Pier",
        bearing_maker=_bearing_maker(str(params["bearing_type"])),
        pier_segments=3,
    )
    bridge.build(model)
    model.loads.set_mass_source(from_elements=True, from_masses=True)
    model.loads.cases.add_modal_eigen("MODAL", num_modes=12)


def _collect(_params: Mapping[str, Any], model: Model) -> dict[str, float]:
    model.results.select_output(cases=["MODAL"])
    periods = model.results.modal_periods()
    return {"t1": float(periods["period"][0])}


def main() -> None:
    _require_sap()
    grid = ParameterGrid(
        {
            "pier_height": [8.0, 12.0],
            "bearing_type": ["ductile", "isolated"],
        }
    )
    with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
        table = run_study(
            client,
            grid,
            build=_build,
            collect=_collect,
            workdir=Path(__file__).with_name("parametric_work"),
            run_cases=["MODAL"],
        )

    print("Height  Bearing   T1(s)")
    for row in table.rows():
        print(f"{row['pier_height']:>6.1f}  {row['bearing_type']:<8}  {row['t1']:>6.3f}")


if __name__ == "__main__":
    main()
