"""Build, analyze, and post-process a steel portal frame.

Run with a local SAP2000 install::

    uv run python examples/portal_frame.py

Demonstrates the everyday M2 API: materials, sections, frames, restraints,
load patterns, a modal case, running the analysis, and pulling results.
"""

from __future__ import annotations

from sap2000py import DOF, SapClient, Units


def main() -> None:
    with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
        m = client.model
        m.files.new_blank(units=Units.KN_M_C)

        # Material and sections.
        m.materials.add_isotropic("STEEL", modulus=2.0e8, poisson=0.3, weight_per_volume=78.5)
        m.frame_sections.add_rectangle("COL", material="STEEL", depth=0.4, width=0.4)
        m.frame_sections.add_rectangle("BEAM", material="STEEL", depth=0.5, width=0.3)

        # Geometry: a 4 m x 3 m portal, fixed at the bases.
        b1 = m.points.add(0, 0, 0)
        b2 = m.points.add(4, 0, 0)
        t1 = m.points.add(0, 0, 3)
        t2 = m.points.add(4, 0, 3)
        m.points.set_restraints(b1, DOF.fixed())
        m.points.set_restraints(b2, DOF.fixed())

        m.frames.add_by_points(b1, t1, section="COL")
        m.frames.add_by_points(b2, t2, section="COL")
        m.frames.add_by_points(t1, t2, section="BEAM")

        # A modal case (mass comes from element self-mass; a blank model
        # already has a default DEAD pattern with self-weight 1.0).
        m.loads.cases.add_modal_eigen("MODAL", num_modes=6)

        # Analyze and report.
        m.analysis.run(cases=["MODAL"])
        periods = m.results.modal_periods()
        print("Mode  Period (s)  Frequency (Hz)")
        for row in periods.rows():
            print(f"{row['mode']:>4}  {row['period']:>10.4f}  {row['frequency']:>13.4f}")


if __name__ == "__main__":
    main()
