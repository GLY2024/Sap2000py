"""Unit tests for S1 bridge-seismic COM wrappers."""

from __future__ import annotations

from typing import Any

from sap2000py import (
    Chinese2010SeismicIntensity,
    DirectionalCombo,
    GeomNonlinearity,
    HistoryLoad,
    HistoryOutputOption,
    ModalCombo,
    RayleighDamping,
    SpectrumLoad,
    TimeIntegration,
)
from sap2000py.model.link_props import DamperDof, FrictionDof, GapHookDof, WenDof


def seismic_responses() -> dict[str, Any]:
    """Fake COM methods used by seismic wrapper tests."""

    def link_force(name: str, item_type: int) -> tuple[Any, ...]:
        if item_type == 2:
            return (
                2,
                ("L1", "L2"),
                ("LE1", "LE2"),
                ("P1", "P2"),
                ("TH", "TH"),
                ("Step", "Step"),
                (0.0, 0.0),
                (1.0, 1.1),
                (2.0, 2.1),
                (3.0, 3.1),
                (4.0, 4.1),
                (5.0, 5.1),
                (6.0, 6.1),
                0,
            )
        return (
            1,
            (name,),
            ("LE1",),
            ("P1",),
            ("TH",),
            ("Step",),
            (0.0,),
            (1.0,),
            (2.0,),
            (3.0,),
            (4.0,),
            (5.0,),
            (6.0,),
            0,
        )

    return {
        "Func.GetNameList": (2, ("RS1", "TH1"), 0),
        "Func.Delete": 0,
        "Func.FuncRS.SetJTGB022013": 0,
        "Func.FuncRS.SetCJJ1662011": 0,
        "Func.FuncRS.SetChinese2010": 0,
        "Func.FuncRS.SetUser": 0,
        "Func.FuncRS.SetFromFile": 0,
        "Func.FuncRS.SetEurocode82004": 0,
        "Func.FuncTH.SetUser": 0,
        "Func.FuncTH.SetFromFile": 0,
        "LoadCases.ModalRitz.SetCase": 0,
        "LoadCases.ModalRitz.SetNumberModes": 0,
        "LoadCases.ModalRitz.SetLoads": 0,
        "LoadCases.ResponseSpectrum.SetCase": 0,
        "LoadCases.ResponseSpectrum.SetModalCase": 0,
        "LoadCases.ResponseSpectrum.SetDampConstant": 0,
        "LoadCases.ResponseSpectrum.SetModalComb_1": 0,
        "LoadCases.ResponseSpectrum.SetDirComb": 0,
        "LoadCases.ResponseSpectrum.SetLoads": 0,
        "LoadCases.ModHistNonLinear.SetCase": 0,
        "LoadCases.ModHistNonLinear.SetModalCase": 0,
        "LoadCases.ModHistNonLinear.SetDampConstant": 0,
        "LoadCases.ModHistNonLinear.SetTimeStep": 0,
        "LoadCases.ModHistNonLinear.SetInitialCase": 0,
        "LoadCases.ModHistNonLinear.SetLoads": 0,
        "LoadCases.ModHistLinear.SetCase": 0,
        "LoadCases.ModHistLinear.SetModalCase": 0,
        "LoadCases.ModHistLinear.SetDampConstant": 0,
        "LoadCases.ModHistLinear.SetTimeStep": 0,
        "LoadCases.ModHistLinear.SetLoads": 0,
        "LoadCases.DirHistNonLinear.SetCase": 0,
        "LoadCases.DirHistNonLinear.SetTimeIntegration": 0,
        "LoadCases.DirHistNonLinear.SetDampProportional": 0,
        "LoadCases.DirHistNonLinear.SetGeometricNonLinearity": 0,
        "LoadCases.DirHistNonLinear.SetInitialCase": 0,
        "LoadCases.DirHistNonLinear.SetTimeStep": 0,
        "LoadCases.DirHistNonLinear.SetLoads": 0,
        "LoadCases.DirHistLinear.SetCase": 0,
        "LoadCases.DirHistLinear.SetTimeIntegration": 0,
        "LoadCases.DirHistLinear.SetDampProportional": 0,
        "LoadCases.DirHistLinear.SetTimeStep": 0,
        "LoadCases.DirHistLinear.SetLoads": 0,
        "LoadCases.StaticNonLinear.SetCase": 0,
        "LoadCases.StaticNonLinear.SetGeometricNonLinearity": 0,
        "LoadCases.StaticNonLinear.SetInitialCase": 0,
        "LoadCases.StaticNonLinear.SetLoads": 0,
        "LoadCases.StaticNonLinear.SetLoadApplication": 0,
        "LoadCases.StaticNonLinear.SetResultsSaved": 0,
        "SourceMass.SetMassSource": 0,
        "PropLink.SetPlasticWen": 0,
        "PropLink.SetFrictionIsolator": 0,
        "PropLink.SetGap": 0,
        "PropLink.SetHook": 0,
        "PropLink.SetDamper": 0,
        "PropLink.SetMultiLinearElastic": 0,
        "PropLink.SetMultiLinearPoints": 0,
        "PropLink.GetNameList": (1, ("LProp",), 0),
        "LinkObj.GetNameList": (2, ("L1", "L2"), 0),
        "GroupDef.GetNameList": (1, ("G",), 0),
        "GroupDef.SetGroup": 0,
        "GroupDef.Delete": 0,
        "LinkObj.SetGroupAssign": 0,
        "Results.LinkForce": link_force,
        "Results.LinkDeformation": (
            1,
            ("L1",),
            ("LE1",),
            ("TH",),
            ("Step",),
            (0.0,),
            (1.0,),
            (2.0,),
            (3.0,),
            (4.0,),
            (5.0,),
            (6.0,),
            0,
        ),
        "Results.BaseReact": (
            1,
            ("TH",),
            ("Step",),
            (0.0,),
            (1.0,),
            (2.0,),
            (3.0,),
            (4.0,),
            (5.0,),
            (6.0,),
            (7.0,),
            (8.0,),
            (9.0,),
            0,
        ),
        "Results.ModalParticipatingMassRatios": (
            1,
            ("MODAL",),
            ("Mode",),
            (1.0,),
            (0.2,),
            (0.1,),
            (0.2,),
            (0.3,),
            (0.1,),
            (0.3,),
            (0.6,),
            (0.0,),
            (0.0,),
            (0.0,),
            (0.0,),
            (0.0,),
            (0.0,),
            0,
        ),
        "Results.Setup.SetOptionModalHist": 0,
        "Results.Setup.SetOptionDirectHist": 0,
        "Results.Setup.SetOptionNLStatic": 0,
    }


def test_response_spectrum_functions_forward_exact_paths(make_model) -> None:
    h = make_model(seismic_responses())
    rs = h.model.functions.rs.add_jtg_b02_2013(
        "JTG", direction=1, peak_accel=0.4, tg=0.45, ci=1.1, cs=0.9, damping=0.05
    )
    h.model.functions.rs.add_cjj_166_2011("CJJ", direction=2, peak_accel=0.3, tg=0.4)
    h.model.functions.rs.add_chinese_2010(
        "CN",
        alpha_max=0.16,
        seismic_intensity=Chinese2010SeismicIntensity.INTENSITY_8_020G,
        tg=0.35,
        period_discount_factor=0.9,
    )
    h.model.functions.rs.add_user("USER", [0.0, 1.0], [0.2, 0.4], damping=0.03)
    h.model.functions.rs.add_from_file("FILE", "rs.txt", head_lines=1, values="frequency")
    h.model.functions.rs.add_eurocode8_2004("EC8", 1, 2, 3)
    h.model.functions.th.add_user("TH", [0.0, 0.1], [1.0, -1.0])
    h.model.functions.th.add_from_file("THF", "th.txt", 1, 2)
    rs.delete()

    assert h.called("Func.FuncRS.SetJTGB022013")[0] == (
        "JTG",
        1,
        0.4,
        0.45,
        1.1,
        0.9,
        0.05,
    )
    assert h.called("Func.FuncRS.SetCJJ1662011")[0] == ("CJJ", 2, 0.3, 0.4, 0.05)
    assert h.called("Func.FuncRS.SetChinese2010")[0] == ("CN", 0.16, 4, 0.35, 0.9, 0.05)
    assert h.called("Func.FuncRS.SetUser")[0] == ("USER", 2, [0.0, 1.0], [0.2, 0.4], 0.03)
    assert h.called("Func.FuncRS.SetFromFile")[0] == ("FILE", "rs.txt", 1, 0.05, 1)
    assert h.called("Func.FuncRS.SetEurocode82004")[0] == ("EC8", 1, 2, 3)
    assert h.called("Func.FuncTH.SetUser")[0] == ("TH", 2, [0.0, 0.1], [1.0, -1.0])
    assert h.called("Func.FuncTH.SetFromFile")[0] == ("THF", "th.txt", 1, 2)
    assert h.called("Func.Delete")[0] == ("JTG",)


def test_load_cases_forward_seismic_case_calls(make_model) -> None:
    h = make_model(seismic_responses())
    h.model.loads.cases.add_modal_ritz(
        "RITZ", loads=[("Accel", "U1"), ("Link", "L1")], num_modes=3
    )
    h.model.loads.cases.add_response_spectrum(
        "RS",
        loads=[SpectrumLoad("U1", "RSFUNC", scale=9.81, csys="Local", angle=30.0)],
        modal_case="RITZ",
        damping=0.04,
        modal_combo=ModalCombo.SRSS,
        directional_combo=DirectionalCombo.ABS,
    )
    h.model.loads.cases.add_modal_history(
        "FNA",
        loads=[HistoryLoad("THFUNC", load="U2", scale=9.81)],
        steps=100,
        dt=0.02,
        modal_case="RITZ",
        initial_case="GRAV",
    )
    h.model.loads.cases.add_direct_history(
        "DIR",
        loads=[HistoryLoad("THFUNC", load="EQ", kind="load", scale=2.0)],
        steps=50,
        dt=0.01,
        damping=RayleighDamping.from_periods(0.5, 1.5, 0.05),
        integration=TimeIntegration.newmark(),
        initial_case="GRAV",
        geometric_nonlinearity=GeomNonlinearity.P_DELTA,
    )
    h.model.loads.cases.add_static_nonlinear(
        "GRAV",
        loads={"DEAD": 1.0},
        initial_case="OLD",
        geometric_nonlinearity=GeomNonlinearity.P_DELTA_LARGE_DISP,
        displacement_control=("P1", "U1", 0.2),
        results_saved="multiple",
    )
    h.model.loads.set_mass_source(from_loads={"DEAD": 1.0}, name="MS", default=True)

    assert h.called("LoadCases.ModalRitz.SetLoads")[0] == (
        "RITZ",
        2,
        ["Accel", "Link"],
        ["U1", "L1"],
        [0, 0],
        [99, 99],
    )
    assert h.called("LoadCases.ResponseSpectrum.SetLoads")[0] == (
        "RS",
        1,
        ["U1"],
        ["RSFUNC"],
        [9.81],
        ["Local"],
        [30.0],
    )
    assert h.called("LoadCases.ResponseSpectrum.SetModalComb_1")[0] == (
        "RS",
        2,
        1.0,
        0.0,
        1,
        60.0,
    )
    assert h.called("LoadCases.ResponseSpectrum.SetDirComb")[0] == ("RS", 2, 0.0)
    assert h.called("LoadCases.ModHistNonLinear.SetLoads")[0] == (
        "FNA",
        1,
        ["Accel"],
        ["U2"],
        ["THFUNC"],
        [9.81],
        [1.0],
        [0.0],
        ["Global"],
        [0.0],
    )
    assert h.called("LoadCases.DirHistNonLinear.SetTimeIntegration")[0] == (
        "DIR",
        1,
        0.0,
        0.25,
        0.5,
        1.0,
        0.0,
    )
    assert h.called("LoadCases.DirHistNonLinear.SetDampProportional")[0] == (
        "DIR",
        2,
        0.0,
        0.0,
        0.5,
        1.5,
        0.05,
        0.05,
    )
    assert h.called("LoadCases.DirHistNonLinear.SetLoads")[0] == (
        "DIR",
        1,
        ["Load"],
        ["EQ"],
        ["THFUNC"],
        [2.0],
        [1.0],
        [0.0],
        ["Global"],
        [0.0],
    )
    assert h.called("LoadCases.StaticNonLinear.SetLoadApplication")[0] == (
        "GRAV",
        2,
        2,
        0.2,
        1,
        1,
        "P1",
        "",
    )
    assert h.called("SourceMass.SetMassSource")[0] == (
        "MS",
        True,
        True,
        True,
        True,
        1,
        ["DEAD"],
        [1.0],
    )


def test_linear_time_history_branches_skip_nonlinear_only_calls(make_model) -> None:
    h = make_model(seismic_responses())

    h.model.loads.cases.add_modal_history(
        "LMH",
        loads=[HistoryLoad("THFUNC", load="U1", scale=1.5)],
        steps=20,
        dt=0.05,
        nonlinear=False,
        initial_case="IGNORED",
    )
    h.model.loads.cases.add_direct_history(
        "LDH",
        loads=[HistoryLoad("THFUNC", load="EQ", kind="load", scale=2.5)],
        steps=10,
        dt=0.1,
        nonlinear=False,
        damping=RayleighDamping.from_coefficients(0.1, 0.2),
        integration=TimeIntegration.wilson(),
        initial_case="IGNORED",
        geometric_nonlinearity=GeomNonlinearity.P_DELTA,
    )

    assert h.called("LoadCases.ModHistLinear.SetCase")[0] == ("LMH",)
    assert h.called("LoadCases.ModHistLinear.SetLoads")[0] == (
        "LMH",
        1,
        ["Accel"],
        ["U1"],
        ["THFUNC"],
        [1.5],
        [1.0],
        [0.0],
        ["Global"],
        [0.0],
    )
    assert h.called("LoadCases.DirHistLinear.SetCase")[0] == ("LDH",)
    assert h.called("LoadCases.DirHistLinear.SetLoads")[0] == (
        "LDH",
        1,
        ["Load"],
        ["EQ"],
        ["THFUNC"],
        [2.5],
        [1.0],
        [0.0],
        ["Global"],
        [0.0],
    )
    assert h.called("LoadCases.ModHistLinear.SetInitialCase") == []
    assert h.called("LoadCases.DirHistLinear.SetInitialCase") == []
    assert h.called("LoadCases.DirHistLinear.SetGeometricNonLinearity") == []


def test_nonlinear_link_props_forward_exact_arrays(make_model) -> None:
    h = make_model(seismic_responses())
    stiffness = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    h.model.link_props.add_plastic_wen("PW", stiffness, nonlinear={"U2": WenDof(100.0, 5.0, 0.1)})
    h.model.link_props.add_friction_isolator(
        "FI", stiffness, nonlinear={"U3": FrictionDof(200.0, 0.02, 0.04, 3.0, 4.0)}
    )
    h.model.link_props.add_gap("GAP", stiffness, nonlinear={"U1": GapHookDof(300.0, 0.01)})
    h.model.link_props.add_hook("HOOK", stiffness, nonlinear={"R1": GapHookDof(400.0, 0.02)})
    h.model.link_props.add_damper("DAMP", stiffness, nonlinear={"U1": DamperDof(500.0, 6.0, 0.5)})
    h.model.link_props.add_multilinear_elastic(
        "MLE", stiffness, curves={"U1": [(0.0, 0.0), (10.0, 0.1)]}
    )

    assert h.called("PropLink.SetPlasticWen")[0] == (
        "PW",
        [True] * 6,
        [False] * 6,
        [False, True, False, False, False, False],
        stiffness,
        [0.0] * 6,
        [0.0, 100.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 5.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.1, 0.0, 0.0, 0.0, 0.0],
        [0.0, 2.0, 0.0, 0.0, 0.0, 0.0],
        0.0,
        0.0,
        "",
    )
    assert h.called("PropLink.SetFrictionIsolator")[0][6:11] == (
        [0.0, 0.0, 200.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.02, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.04, 0.0, 0.0, 0.0],
        [0.0, 0.0, 3.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 4.0, 0.0, 0.0, 0.0],
    )
    assert h.called("PropLink.SetGap")[0][6:8] == (
        [300.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.01, 0.0, 0.0, 0.0, 0.0, 0.0],
    )
    assert h.called("PropLink.SetHook")[0][6:8] == (
        [0.0, 0.0, 0.0, 400.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.02, 0.0, 0.0],
    )
    assert h.called("PropLink.SetDamper")[0][6:9] == (
        [500.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [6.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
    )
    assert h.called("PropLink.SetMultiLinearElastic")[0][3] == [
        True,
        False,
        False,
        False,
        False,
        False,
    ]
    assert h.called("PropLink.SetMultiLinearPoints")[0] == (
        "MLE",
        1,
        2,
        [0.0, 10.0],
        [0.0, 0.1],
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )


def test_results_link_base_modal_and_output_options(make_model) -> None:
    h = make_model(seismic_responses())
    link_forces = h.model.results.link_forces("L1")
    link_deformations = h.model.results.link_deformations("L1")
    base = h.model.results.base_reactions()
    modal = h.model.results.modal_participating_mass_ratios()
    h.model.results.set_modal_history_output(HistoryOutputOption.STEP_BY_STEP)
    h.model.results.set_direct_history_output(HistoryOutputOption.LAST_STEP)
    h.model.results.set_nl_static_output(HistoryOutputOption.ENVELOPES)

    assert link_forces["P"] == (1.0,)
    assert link_deformations["U1"] == (1.0,)
    assert base["FX"] == (1.0,)
    assert modal["SumUZ"] == (0.6,)
    assert h.called("Results.LinkForce")[0] == ("L1", 0)
    assert h.called("Results.LinkDeformation")[0] == ("L1", 0)
    assert h.called("Results.BaseReact")[0] == ()
    assert h.called("Results.ModalParticipatingMassRatios")[0] == ()
    assert h.called("Results.Setup.SetOptionModalHist")[0] == (2,)
    assert h.called("Results.Setup.SetOptionDirectHist")[0] == (3,)
    assert h.called("Results.Setup.SetOptionNLStatic")[0] == (1,)


def test_result_batch_collects_link_temp_group(make_model) -> None:
    h = make_model(seismic_responses())
    tables = (
        h.model.results.batch()
        .link_forces(links=["L1", "L2"], strategy="temporary_group")
        .collect()
    )

    assert tables["link_forces"]["link"] == ("L1", "L2")
    assert len(h.called("GroupDef.SetGroup")) == 1
    assert [call[:2] for call in h.called("LinkObj.SetGroupAssign")] == [
        ("L1", h.called("GroupDef.SetGroup")[0][0]),
        ("L2", h.called("GroupDef.SetGroup")[0][0]),
    ]
    assert h.called("Results.LinkForce")[0][1] == 2
