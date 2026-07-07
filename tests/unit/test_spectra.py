from __future__ import annotations

import math

import numpy as np
import pytest

from sap2000py.seismic import (
    IM_REGISTRY,
    GroundMotionRecord,
    intensity_measure,
    jtg2231_spectrum,
    response_spectrum,
    sa,
    sa_avg,
)


def test_response_spectrum_constant_acceleration_matches_analytic_solution() -> None:
    amplitude = 0.1
    dt = 0.005
    duration = 5.0
    period = 1.0
    damping = 0.05
    accel = np.full(int(duration / dt) + 1, amplitude, dtype=np.float64)
    record = GroundMotionRecord("constant", dt, accel)

    spectrum = response_spectrum(record, periods=[period], damping=damping)

    omega = 2.0 * math.pi / period
    root = math.sqrt(1.0 - damping * damping)
    omega_d = omega * root
    times = record.times
    relative = -amplitude / omega**2 * (
        1.0
        - np.exp(-damping * omega * times)
        * (np.cos(omega_d * times) + damping / root * np.sin(omega_d * times))
    )
    expected = float(np.max(np.abs(omega**2 * relative)))
    assert spectrum.values[0] == pytest.approx(expected, rel=1e-10)


def test_short_period_sa_approaches_pga() -> None:
    dt = 0.001
    times = np.arange(0.0, 1.0 + dt, dt)
    accel = 0.25 * np.sin(2.0 * np.pi * 2.0 * times)
    record = GroundMotionRecord("sine", dt, accel)

    assert sa(record, 0.01) == pytest.approx(record.pga, rel=0.06)


def test_sa_avg_is_geometric_mean_of_spectrum_values() -> None:
    dt = 0.01
    times = np.arange(0.0, 4.0 + dt, dt)
    record = GroundMotionRecord("mixed", dt, 0.2 * np.sin(2.0 * np.pi * times))
    periods = np.asarray([0.2, 0.5, 1.0], dtype=np.float64)
    spectrum = response_spectrum(record, periods=periods)

    assert sa_avg(record, periods) == pytest.approx(float(np.exp(np.mean(np.log(spectrum.values)))))


def test_intensity_measure_registry_binds_parameters() -> None:
    record = GroundMotionRecord("pulse", 0.1, np.asarray([0.0, 0.2, 0.0], dtype=np.float64))

    assert IM_REGISTRY["pga"](record) == pytest.approx(0.2)
    assert intensity_measure("sa_t1", period=0.5)(record) == pytest.approx(sa(record, 0.5))
    assert intensity_measure("sa_avg", periods=[0.2, 0.5])(record) == pytest.approx(
        sa_avg(record, [0.2, 0.5])
    )


def test_jtg2231_spectrum_plateau_and_corners() -> None:
    damping = 0.05
    peak_accel = 0.4
    ci = 1.2
    cs = 0.9
    tg = 0.4
    spectrum = jtg2231_spectrum(
        peak_accel=peak_accel,
        tg=tg,
        ci=ci,
        cs=cs,
        damping=damping,
        t_max=0.8,
        dt=0.1,
    )
    smax = 2.5 * ci * cs * peak_accel

    assert spectrum.sa(0.0) == pytest.approx(0.6 * smax)
    assert spectrum.sa(0.1) == pytest.approx(smax)
    assert spectrum.sa(tg) == pytest.approx(smax)
    assert spectrum.sa(2.0 * tg) == pytest.approx(0.5 * smax)
    assert spectrum.damping == pytest.approx(damping)


@pytest.mark.parametrize(
    ("damping", "cd"),
    [
        (0.02, 1.2678571428571428),
        (0.10, 0.7916666666666667),
        (0.35, 0.55),
    ],
)
def test_jtg2231_cd_formula_and_floor(damping: float, cd: float) -> None:
    peak_accel = 0.4
    tg = 0.4
    spectrum = jtg2231_spectrum(
        peak_accel=peak_accel,
        tg=tg,
        damping=damping,
        t_max=tg,
        dt=0.1,
    )

    assert spectrum.sa(tg) / (2.5 * peak_accel) == pytest.approx(cd)
