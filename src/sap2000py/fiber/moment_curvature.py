"""Moment-curvature analysis of a fiber section under constant axial load.

For each imposed curvature the solver finds the axial strain ``eps0`` that
equilibrates the applied axial load, then records the resisting moment. The
result is the moment-curvature curve, with a helper to idealize it as a
bilinear (equal-energy) relationship.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from .section import FiberSection


class MomentCurvatureError(RuntimeError):
    """Base exception for moment-curvature analysis errors."""


class EquilibriumError(MomentCurvatureError):
    """Raised when no axial strain equilibrates the section at a curvature."""


class ConvergenceError(MomentCurvatureError):
    """Raised when the axial-strain solver exhausts its iteration budget."""


class MomentCurvatureTermination(Enum):
    """Reason a moment-curvature analysis stopped."""

    COMPLETED = "completed"
    SECTION_FAILED = "section_failed"


def _solve_eps0(section: FiberSection, phi: float, axial: float) -> float:
    """Find eps0 so that the section's axial force equals ``axial`` (bisection)."""

    def residual(eps0: float) -> float:
        return section.response(eps0, phi)[0] - axial

    lo, hi = -0.05, 0.05
    r_lo, r_hi = residual(lo), residual(hi)
    # Expand the bracket until the residual changes sign (or give up).
    for _ in range(60):
        if r_lo * r_hi <= 0:
            break
        lo *= 1.5
        hi *= 1.5
        r_lo, r_hi = residual(lo), residual(hi)
    else:
        raise EquilibriumError(f"no equilibrium at curvature {phi:g}")

    for _ in range(100):
        mid = 0.5 * (lo + hi)
        r_mid = residual(mid)
        if abs(r_mid) < 1e-6 * (abs(axial) + 1.0):
            return mid
        if r_lo * r_mid <= 0:
            hi, r_hi = mid, r_mid
        else:
            lo, r_lo = mid, r_mid
    raise ConvergenceError(f"axial-strain solver did not converge at curvature {phi:g}")


@dataclass(frozen=True)
class MomentCurvature:
    """Moment-curvature result.

    Attributes
    ----------
    curvature, moment:
        Paired arrays describing the M-phi curve.
    axial:
        The constant axial load used (tension-positive).
    termination:
        ``COMPLETED`` when every requested curvature was equilibrated, or
        ``SECTION_FAILED`` when equilibrium was lost after the initial point.
    """

    curvature: NDArray[np.float64]
    moment: NDArray[np.float64]
    axial: float
    termination: MomentCurvatureTermination

    def bilinearize(self) -> tuple[float, float, float, float]:
        """Idealize as an equal-energy bilinear curve.

        Returns ``(phi_y, M_y, phi_u, M_u)``: the yield curvature/moment of the
        idealized bilinear and the ultimate curvature/moment (the last point).
        The bilinear has the same enclosed area as the actual curve up to
        ultimate, with an effective elastic stiffness taken as the **maximum
        secant stiffness** of the curve. Using the maximum secant guarantees the
        actual curve lies on or below the elastic line everywhere, so the
        equal-area yield point is always real and ``phi_y <= phi_u`` (with
        equality only for a perfectly linear curve).
        """
        phi = self.curvature
        m = self.moment
        if len(phi) < 2:
            raise ValueError("need at least two points to bilinearize.")
        phi_u, m_u = float(phi[-1]), float(m[-1])
        area = float(np.trapezoid(m, phi))
        nonzero = phi > 0
        k0 = float(np.max(m[nonzero] / phi[nonzero]))  # max secant stiffness
        if k0 <= 0:
            return 0.0, 0.0, phi_u, m_u
        # Equal-area: M_y*(phi_u - 0.5*phi_y) = area with M_y = k0 * phi_y.
        discriminant = max(phi_u**2 - 2.0 * area / k0, 0.0)
        phi_y = phi_u - math.sqrt(discriminant)
        return float(phi_y), float(k0 * phi_y), phi_u, m_u


def moment_curvature(
    section: FiberSection,
    *,
    max_curvature: float,
    axial: float = 0.0,
    n_steps: int = 50,
) -> MomentCurvature:
    """Compute the moment-curvature curve of ``section`` under constant axial load.

    Parameters
    ----------
    section:
        The discretized fiber section.
    max_curvature:
        Largest curvature to analyze (1/length).
    axial:
        Constant axial load held during the analysis (tension-positive).
    n_steps:
        Number of curvature increments from 0 to ``max_curvature``.

    Notes
    -----
    If equilibrium is lost after the initial point, the analysis returns the
    preceding truncated curve with ``termination`` set to ``SECTION_FAILED``.
    Failure at zero curvature instead raises :class:`EquilibriumError`, because
    the requested axial load cannot be carried.
    """
    if isinstance(section, FiberSection) and len(section) == 0:
        raise ValueError("section must contain at least one fiber.")
    if n_steps < 1:
        raise ValueError("n_steps must be >= 1.")
    if max_curvature <= 0:
        raise ValueError("max_curvature must be positive.")
    curvatures = np.linspace(0.0, max_curvature, n_steps + 1)
    phis: list[float] = []
    moments: list[float] = []
    termination = MomentCurvatureTermination.COMPLETED
    for index, phi in enumerate(curvatures):
        try:
            eps0 = _solve_eps0(section, float(phi), axial)
        except EquilibriumError as error:
            if index == 0:
                raise EquilibriumError(
                    f"cannot equilibrate axial load {axial:g} at zero curvature"
                ) from error
            termination = MomentCurvatureTermination.SECTION_FAILED
            break
        _n, moment = section.response(eps0, float(phi))
        phis.append(float(phi))
        moments.append(moment)
    return MomentCurvature(
        curvature=np.asarray(phis, dtype=float),
        moment=np.asarray(moments, dtype=float),
        axial=float(axial),
        termination=termination,
    )
