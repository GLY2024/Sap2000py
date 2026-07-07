"""Response spectra and scalar seismic intensity measures."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .ground_motion import GroundMotionRecord


@dataclass(frozen=True)
class Spectrum:
    """Response spectrum values at discrete periods.

    Attributes
    ----------
    periods:
        Periods in seconds.
    values:
        Spectral accelerations in ``g``.
    damping:
        Critical damping ratio.
    """

    periods: NDArray[np.float64]
    values: NDArray[np.float64]
    damping: float

    def __post_init__(self) -> None:
        periods = np.asarray(self.periods, dtype=np.float64)
        values = np.asarray(self.values, dtype=np.float64)
        if periods.ndim != 1 or values.ndim != 1 or len(periods) != len(values):
            raise ValueError("periods and values must be one-dimensional arrays of equal length.")
        if np.any(periods < 0):
            raise ValueError("periods must be non-negative.")
        if self.damping < 0:
            raise ValueError("damping must be non-negative.")
        order = np.argsort(periods)
        object.__setattr__(self, "periods", periods[order])
        object.__setattr__(self, "values", values[order])
        object.__setattr__(self, "damping", float(self.damping))

    def sa(self, period: float) -> float:
        """Interpolate spectral acceleration at ``period``."""
        return float(np.interp(float(period), self.periods, self.values))


@dataclass(frozen=True)
class DesignSpectrum(Spectrum):
    """A code-defined design response spectrum."""


def response_spectrum(
    record: GroundMotionRecord,
    *,
    periods: Sequence[float] | NDArray[np.float64] | None = None,
    damping: float = 0.05,
) -> Spectrum:
    """Compute a pseudo-acceleration response spectrum.

    The recurrence is the Nigam-Jennings piecewise-exact state transition for a
    linearly interpolated ground-acceleration input. It is vectorized over
    oscillator periods and returns pseudo-acceleration ``Sa`` in ``g``.
    """
    if damping < 0 or damping >= 1:
        raise ValueError("damping must satisfy 0 <= damping < 1.")
    periods_array = (
        np.logspace(-2.0, 1.0, 200, dtype=np.float64)
        if periods is None
        else np.asarray(periods, dtype=np.float64)
    )
    if periods_array.ndim != 1 or np.any(periods_array <= 0):
        raise ValueError("periods must be a one-dimensional array of positive values.")
    values = _nigam_jennings(record.accel, record.dt, periods_array, damping)
    return Spectrum(periods=periods_array, values=values, damping=damping)


def sa(record: GroundMotionRecord, period: float, *, damping: float = 0.05) -> float:
    """Return spectral acceleration in ``g`` at one period."""
    return response_spectrum(record, periods=[period], damping=damping).sa(period)


def sa_avg(
    record: GroundMotionRecord,
    periods: Sequence[float] | NDArray[np.float64],
    *,
    damping: float = 0.05,
) -> float:
    """Return the geometric mean of spectral acceleration over ``periods``."""
    spectrum = response_spectrum(record, periods=periods, damping=damping)
    if np.any(spectrum.values <= 0):
        return 0.0
    return float(np.exp(np.mean(np.log(spectrum.values))))


def _nigam_jennings(
    accel: NDArray[np.float64],
    dt: float,
    periods: NDArray[np.float64],
    damping: float,
) -> NDArray[np.float64]:
    omega = 2.0 * np.pi / periods
    omega2 = omega * omega
    root = math.sqrt(1.0 - damping * damping)
    omega_d = omega * root
    decay = np.exp(-damping * omega * dt)
    sin = np.sin(omega_d * dt)
    cos = np.cos(omega_d * dt)

    e11 = decay * (cos + damping / root * sin)
    e12 = decay * sin / omega_d
    e21 = -decay * omega / root * sin
    e22 = decay * (cos - damping / root * sin)

    j0_u = (e11 - 1.0) / omega2
    j0_v = e21 / omega2
    eb_u = -e12
    eb_v = -e22
    q_u = dt * eb_u - j0_u
    q_v = dt * eb_v - j0_v
    j1_u = (-2.0 * damping * omega * q_u - q_v) / omega2
    j1_v = q_u
    slope_u = dt * j0_u - j1_u
    slope_v = dt * j0_v - j1_v

    u = np.zeros_like(periods, dtype=np.float64)
    v = np.zeros_like(periods, dtype=np.float64)
    max_u = np.zeros_like(periods, dtype=np.float64)
    for a0, a1 in pairwise(accel):
        slope = (float(a1) - float(a0)) / dt
        next_u = e11 * u + e12 * v + float(a0) * j0_u + slope * slope_u
        next_v = e21 * u + e22 * v + float(a0) * j0_v + slope * slope_v
        u = next_u
        v = next_v
        max_u = np.maximum(max_u, np.abs(u))
    return omega2 * max_u


def _im_pga(record: GroundMotionRecord, **_: Any) -> float:
    return record.pga


def _im_pgv(record: GroundMotionRecord, **_: Any) -> float:
    return record.pgv()


def _im_sa_t1(record: GroundMotionRecord, *, period: float, damping: float = 0.05) -> float:
    return sa(record, period, damping=damping)


def _im_sa_avg(
    record: GroundMotionRecord,
    *,
    periods: Sequence[float] | NDArray[np.float64],
    damping: float = 0.05,
) -> float:
    return sa_avg(record, periods, damping=damping)


IM_REGISTRY: dict[str, Callable[..., float]] = {
    "pga": _im_pga,
    "pgv": _im_pgv,
    "sa_t1": _im_sa_t1,
    "sa_avg": _im_sa_avg,
}


def intensity_measure(name: str, **params: Any) -> Callable[[GroundMotionRecord], float]:
    """Return an intensity-measure callable with parameters bound."""
    if name not in IM_REGISTRY:
        raise KeyError(name)

    def measure(record: GroundMotionRecord) -> float:
        return IM_REGISTRY[name](record, **params)

    return measure


def jtg2231_spectrum(
    *,
    peak_accel: float,
    tg: float,
    ci: float = 1.0,
    cs: float = 1.0,
    cd: float | None = None,
    damping: float = 0.05,
    t_max: float = 10.0,
    dt: float = 0.01,
) -> DesignSpectrum:
    """Return the JTG/T 2231-01-2020 design spectrum.

    ``Smax = 2.5 * Ci * Cs * Cd * A``. The spectrum starts at ``0.6 * Smax``,
    rises linearly to ``Smax`` at 0.1 s, stays flat to ``Tg``, then decays as
    ``Smax * Tg / T``.
    """
    if peak_accel < 0 or tg <= 0 or damping <= 0 or t_max <= 0 or dt <= 0:
        raise ValueError("require peak_accel >= 0 and positive tg, damping, t_max, dt.")
    # JTG/T 2231-01-2020 §5.2.1 (spectrum shape), §5.2.2 (Smax), §5.2.4 (Cd).
    cd_value = (
        max(0.55, 1.0 + (0.05 - damping) / (0.08 + 1.6 * damping))
        if cd is None
        else float(cd)
    )
    smax = 2.5 * float(ci) * float(cs) * cd_value * float(peak_accel)
    periods = np.arange(0.0, t_max + 0.5 * dt, dt, dtype=np.float64)
    values = np.empty_like(periods)
    values[periods <= 0.1] = smax * (0.6 + 0.4 * periods[periods <= 0.1] / 0.1)
    plateau = (periods > 0.1) & (periods <= tg)
    values[plateau] = smax
    decay = periods > tg
    values[decay] = smax * tg / periods[decay]
    return DesignSpectrum(periods=periods, values=values, damping=damping)
