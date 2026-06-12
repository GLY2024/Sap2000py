"""Unit tests for the fiber computation core (pure NumPy, no COM)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from sap2000py.fiber import (
    BilinearSteel,
    FiberSection,
    LinearElastic,
    ManderConcrete,
    moment_curvature,
)

# -- constitutive models ----------------------------------------------------


def test_bilinear_steel_elastic_then_yield() -> None:
    steel = BilinearSteel(E=2.0e5, fy=400.0, hardening=0.01)
    assert steel.eps_y == pytest.approx(0.002)
    assert float(steel.stress(0.001)) == pytest.approx(200.0)  # elastic
    assert float(steel.stress(0.002)) == pytest.approx(400.0)  # at yield
    # 1% hardening: at twice yield strain, stress = fy + 0.01*E*ey
    assert float(steel.stress(0.004)) == pytest.approx(400.0 + 0.01 * 2.0e5 * 0.002)


def test_bilinear_steel_symmetric_in_compression() -> None:
    steel = BilinearSteel(E=2.0e5, fy=400.0)
    assert float(steel.stress(-0.001)) == pytest.approx(-200.0)


def test_bilinear_steel_rupture() -> None:
    steel = BilinearSteel(E=2.0e5, fy=400.0, eps_ult=0.05)
    assert float(steel.stress(0.06)) == 0.0


def test_mander_peak_and_tension() -> None:
    conc = ManderConcrete(fco=40.0, Ec=3.0e4)
    # No tension capacity.
    assert float(conc.stress(0.001)) == 0.0
    # Peak (magnitude) at eps_cc (unconfined: eps_co = 0.002).
    peak = float(conc.stress(-conc.eps_cc))
    assert peak == pytest.approx(-40.0, rel=1e-6)


def test_mander_crushes_beyond_eps_cu() -> None:
    conc = ManderConcrete(fco=40.0, Ec=3.0e4, eps_cu=0.004)
    assert float(conc.stress(-0.005)) == 0.0


def test_mander_confined_has_higher_peak_strain() -> None:
    unconf = ManderConcrete(fco=40.0, Ec=3.0e4)
    conf = ManderConcrete(fco=40.0, fcc=52.0, Ec=3.0e4)
    assert conf.eps_cc > unconf.eps_cc


# -- fiber section & response -----------------------------------------------


def test_response_pure_axial_linear() -> None:
    sec = FiberSection()
    mat = LinearElastic(E=1000.0)
    sec.add_rect_patch(mat, y_min=-1.0, y_max=1.0, width=1.0, n=10)  # area = 2.0
    n, m = sec.response(eps0=0.001, phi=0.0)
    assert n == pytest.approx(1000.0 * 2.0 * 0.001)  # E*A*eps
    assert m == pytest.approx(0.0, abs=1e-9)  # symmetric -> no moment


def test_response_elastic_EI() -> None:
    # Rectangular elastic section: M = E * I * phi, I = b*h^3/12.
    b, h, E = 0.3, 0.6, 3.0e7
    sec = FiberSection()
    sec.add_rect_patch(LinearElastic(E), y_min=-h / 2, y_max=h / 2, width=b, n=400)
    inertia = b * h**3 / 12.0
    phi = 1e-4
    _n, m = sec.response(eps0=0.0, phi=phi)
    assert m == pytest.approx(E * inertia * phi, rel=1e-3)


# -- moment-curvature -------------------------------------------------------


def test_moment_curvature_elastic_is_linear() -> None:
    b, h, E = 0.3, 0.6, 3.0e7
    sec = FiberSection()
    sec.add_rect_patch(LinearElastic(E), y_min=-h / 2, y_max=h / 2, width=b, n=400)
    inertia = b * h**3 / 12.0
    mc = moment_curvature(sec, max_curvature=1e-3, axial=0.0, n_steps=10)
    # M should equal E*I*phi across the whole range.
    expected = E * inertia * mc.curvature
    assert np.allclose(mc.moment, expected, rtol=1e-3)


def test_moment_curvature_axial_offsets_neutral_axis() -> None:
    b, h, E = 0.3, 0.6, 3.0e7
    sec = FiberSection()
    sec.add_rect_patch(LinearElastic(E), y_min=-h / 2, y_max=h / 2, width=b, n=200)
    # With axial tension, eps0 must be positive to carry it; moment still linear.
    mc = moment_curvature(sec, max_curvature=1e-3, axial=1.0e5, n_steps=5)
    inertia = b * h**3 / 12.0
    assert np.allclose(mc.moment, E * inertia * mc.curvature, rtol=1e-3)


def test_moment_curvature_rc_yields_and_bilinearizes() -> None:
    # A simple singly-symmetric RC section in consistent N, mm, MPa units.
    sec = FiberSection()
    conc = ManderConcrete(fco=40.0, Ec=3.0e4, eps_cu=0.005)
    sec.add_rect_patch(conc, y_min=-300, y_max=300, width=500, n=60)
    steel = BilinearSteel(E=2.0e5, fy=400.0)
    sec.add_bars(steel, ys=[-250, 250], area_each=1500.0)

    mc = moment_curvature(sec, max_curvature=3e-5, axial=-2.0e6, n_steps=60)
    assert len(mc.curvature) > 5
    # Moment is positive and generally increasing into the plastic range.
    assert mc.moment[-1] > 0
    phi_y, m_y, phi_u, m_u = mc.bilinearize()
    assert 0 < phi_y < phi_u
    assert m_y > 0 and m_u > 0
    assert math.isfinite(m_y)
