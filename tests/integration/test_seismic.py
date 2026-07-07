"""Integration tests for the bridge-seismic extension against real SAP2000.

Run with ``pytest --sap``. These tests intentionally cover the COM surfaces
that unit tests can only fake: code/user spectra, function file import, modal
and direct nonlinear time-history cases, nonlinear links, and extended result
tables.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sap2000py import (
    Chinese2010SeismicIntensity,
    HistoryLoad,
    HistoryOutputOption,
    RayleighDamping,
    SapClient,
    SpectrumLoad,
    TimeIntegration,
    Units,
)
from sap2000py.bridge import ContinuousGirderBridge, LeadRubberBearing
from sap2000py.model.results import ResultTable
from sap2000py.seismic import gravity, jtg2231_spectrum

pytestmark = pytest.mark.sap


def _build_bridge(m, *, nonlinear_bearings: bool = False) -> tuple[str, str, str]:
    """Build a two-span concrete bridge and return girder frame, base point, link."""
    m.files.new_blank(units=Units.KN_M_C)
    m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
    m.frame_sections.add_rectangle("Girder", material="C40", depth=1.6, width=5.0)
    m.frame_sections.add_rectangle("Pier", material="C40", depth=1.4, width=1.4)

    def bearing_maker(name: str, x: float, y: float, z: float) -> LeadRubberBearing:
        return LeadRubberBearing(
            name,
            x,
            y,
            z,
            vertical_stiffness=1.0e9,
            shear_stiffness=2.0e5,
            yield_force=250.0,
            post_yield_ratio=0.12,
        )

    bridge = ContinuousGirderBridge(
        "SB",
        spans=[24.0, 24.0],
        pier_height=8.0,
        girder_section="Girder",
        pier_section="Pier",
        bearing_stiffness=None if nonlinear_bearings else [1e9, 2e5, 2e5, 1e8, 1e8, 1e8],
        bearing_maker=bearing_maker if nonlinear_bearings else None,
        pier_segments=2,
    )
    build = bridge.build(m)
    girder = "SB_girder_e0"
    base = "SB_F1_base"
    link = build.bearings[1].name
    # LeadRubberBearing passes its component name as the LinkObj user name; v25
    # creates the corresponding link element as SB_B1 on this blank model.
    assert link in set(m.links.names())
    m.frames.ref(girder).set_output_stations(min_stations=3)
    return girder, base, link


def _has_nonzero(table: ResultTable, columns: tuple[str, ...]) -> bool:
    for column in columns:
        if column in table.names and any(abs(float(value)) > 1.0e-9 for value in table[column]):
            return True
    return False


def _assert_table(table: ResultTable, columns: set[str]) -> None:
    assert len(table) > 0
    assert set(table.names) >= columns


def test_response_spectrum_functions_and_results(client: SapClient, tmp_path: Path) -> None:
    m = client.model
    girder, _base, _link = _build_bridge(m)

    jtg = m.functions.rs.add_jtg_b02_2013(
        "JTG_B02", direction=1, peak_accel=0.2, tg=0.35, ci=1.0, cs=1.0
    )
    spectrum = jtg2231_spectrum(peak_accel=0.2, tg=0.35, t_max=1.0, dt=0.05)
    user = m.functions.rs.add_user(
        "USER_JTG2231", spectrum.periods.tolist(), spectrum.values.tolist()
    )
    m.functions.rs.add_cjj_166_2011("CJJ_166", direction=1, peak_accel=0.2, tg=0.35)
    m.functions.rs.add_chinese_2010(
        "CHINESE_2010",
        alpha_max=0.16,
        seismic_intensity=Chinese2010SeismicIntensity.INTENSITY_8_020G,
        tg=0.35,
        period_discount_factor=0.9,
    )
    assert {"JTG_B02", "USER_JTG2231", "CJJ_166", "CHINESE_2010"} <= set(
        m.functions.names()
    )

    m.loads.cases.add_modal_eigen("MODAL", num_modes=6)
    m.loads.cases.add_response_spectrum(
        "RS_JTG",
        modal_case="MODAL",
        loads=[SpectrumLoad("U1", jtg, scale=gravity(m.current_units))],
    )
    m.loads.cases.add_response_spectrum(
        "RS_USER",
        modal_case="MODAL",
        loads=[SpectrumLoad("U1", user, scale=gravity(m.current_units))],
    )
    m.files.save(tmp_path / "seismic_rs.sdb")

    report = m.analysis.run(cases=["MODAL", "RS_JTG", "RS_USER"])
    assert report.status["RS_JTG"] == "finished"
    assert report.status["RS_USER"] == "finished"
    m.results.select_output(cases=["RS_JTG", "RS_USER"])

    base = m.results.base_reactions()
    forces = m.results.frame_forces(girder)
    _assert_table(base, {"case", "FX", "FY", "FZ", "MX", "MY", "MZ"})
    _assert_table(forces, {"frame", "station", "P", "V2", "V3", "M2", "M3"})
    assert _has_nonzero(base, ("FX", "FY", "FZ", "MX", "MY", "MZ"))
    assert _has_nonzero(forces, ("P", "V2", "V3", "M2", "M3"))


def test_functions_from_file(client: SapClient, tmp_path: Path) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    th_file = tmp_path / "tiny_th.txt"
    th_file.write_text("0.00 0.0\n0.02 0.1\n0.04 -0.1\n0.06 0.0\n", encoding="utf-8")
    rs_file = tmp_path / "tiny_rs.txt"
    rs_file.write_text("0.00 0.10\n0.20 0.30\n1.00 0.05\n", encoding="utf-8")

    m.functions.th.add_from_file(
        "TH_FILE",
        th_file,
        head_lines=0,
        prefix_chars=0,
        points_per_line=2,
        value_type=1,
        free_format=True,
        number_fixed=10,
        dt=0.02,
    )
    m.functions.rs.add_from_file("RS_FILE", rs_file, head_lines=0, damping=0.05)

    assert {"TH_FILE", "RS_FILE"} <= set(m.functions.names())


def test_modal_history_fna_with_lrb_and_link_results(
    client: SapClient, tmp_path: Path
) -> None:
    m = client.model
    _girder, _base, link = _build_bridge(m, nonlinear_bearings=True)
    m.loads.patterns.set_self_weight("DEAD", 1.0)
    m.loads.cases.add_static_nonlinear("GRAV", loads={"DEAD": 1.0})
    m.loads.cases.add_modal_ritz("RITZ", num_modes=6, loads=[("Accel", "UX"), ("Link", link)])
    th = m.functions.th.add_user("EQ_FNA", [0.0, 0.02, 0.04, 0.06], [0.0, 0.08, -0.08, 0.0])
    m.loads.cases.add_modal_history(
        "FNA",
        modal_case="RITZ",
        initial_case="GRAV",
        nonlinear=True,
        loads=[HistoryLoad(th, load="U1", scale=gravity(m.current_units))],
        steps=80,
        dt=0.02,
    )
    m.results.set_modal_history_output(HistoryOutputOption.STEP_BY_STEP)
    m.files.save(tmp_path / "seismic_fna.sdb")

    report = m.analysis.run(cases=["GRAV", "RITZ", "FNA"])
    assert report.status["FNA"] == "finished"

    m.results.select_output(cases=["RITZ"])
    mass = m.results.modal_participating_mass_ratios()
    _assert_table(mass, {"case", "mode", "period", "UX", "UY", "SumUX"})

    m.results.select_output(cases=["FNA"])
    deformations = m.results.link_deformations(link)
    forces = m.results.link_forces(link)
    _assert_table(deformations, {"link", "case", "step", "U1", "U2", "U3"})
    _assert_table(forces, {"link", "point", "case", "step", "P", "V2", "V3"})


def test_direct_integration_nlth_with_gravity_initial_case(
    client: SapClient, tmp_path: Path
) -> None:
    m = client.model
    _girder, base, _link = _build_bridge(m, nonlinear_bearings=True)
    m.loads.patterns.set_self_weight("DEAD", 1.0)
    m.loads.cases.add_static_nonlinear("GRAV", loads={"DEAD": 1.0})
    th = m.functions.th.add_user("EQ_DIR", [0.0, 0.02, 0.04, 0.06], [0.0, 0.06, -0.06, 0.0])
    m.loads.cases.add_direct_history(
        "DIR",
        initial_case="GRAV",
        nonlinear=True,
        loads=[HistoryLoad(th, load="U1", scale=gravity(m.current_units))],
        steps=80,
        dt=0.02,
        damping=RayleighDamping.from_periods(0.2, 1.0, 0.05),
        integration=TimeIntegration.hht(alpha=0.0),
    )
    m.results.set_direct_history_output(HistoryOutputOption.STEP_BY_STEP)
    m.files.save(tmp_path / "seismic_dir.sdb")

    report = m.analysis.run(cases=["GRAV", "DIR"])
    assert report.status["DIR"] == "finished"
    m.results.select_output(cases=["DIR"])

    displacements = m.results.joint_displacements(base)
    base_reactions = m.results.base_reactions()
    _assert_table(displacements, {"joint", "case", "step", "U1", "U2", "U3"})
    _assert_table(base_reactions, {"case", "step", "FX", "FY", "FZ", "MX", "MY", "MZ"})
    assert _has_nonzero(base_reactions, ("FX", "FY", "FZ", "MX", "MY", "MZ"))


def test_ec8_spectrum_function_signature(client: SapClient) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)

    m.functions.rs.add_eurocode8_2004(
        "EC8_2004",
        ground_type=1,
        spectrum_type=1,
        ag=0.25,
        beta=0.2,
        q=1.0,
        damping=0.05,
    )

    assert "EC8_2004" in set(m.functions.names())
