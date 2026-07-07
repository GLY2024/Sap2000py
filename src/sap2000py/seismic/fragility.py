"""Fragility-model fitting utilities."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .._optional import require


@dataclass(frozen=True)
class Psdm:
    """Probabilistic seismic demand model.

    Attributes
    ----------
    ln_a:
        Intercept in ``ln(D) = ln_a + b * ln(IM)``.
    b:
        Slope in ``ln(D) = ln_a + b * ln(IM)``.
    beta:
        Conditional demand dispersion ``beta_D|IM``.
    """

    ln_a: float
    b: float
    beta: float

    def median_im(self, capacity: float) -> float:
        """Return the median IM at which median demand reaches ``capacity``."""
        if capacity <= 0.0:
            raise ValueError("capacity must be positive.")
        return float(math.exp((math.log(capacity) - self.ln_a) / self.b))


def fit_psdm(
    im: Sequence[float] | NDArray[np.float64],
    edp: Sequence[float] | NDArray[np.float64],
) -> Psdm:
    """Fit ``ln(EDP) = ln_a + b * ln(IM)`` by least squares."""
    im_array = np.asarray(im, dtype=np.float64)
    edp_array = np.asarray(edp, dtype=np.float64)
    if im_array.shape != edp_array.shape or im_array.ndim != 1:
        raise ValueError("im and edp must be one-dimensional arrays of equal length.")
    if im_array.size < 3:
        raise ValueError("at least three demand points are required.")
    if np.any(im_array <= 0.0) or np.any(edp_array <= 0.0):
        raise ValueError("im and edp values must be positive.")
    x = np.log(im_array)
    y = np.log(edp_array)
    matrix = np.column_stack((np.ones_like(x), x))
    ln_a, b = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residuals = y - (ln_a + b * x)
    beta = math.sqrt(float(np.sum(residuals * residuals)) / float(im_array.size - 2))
    return Psdm(float(ln_a), float(b), float(beta))


@dataclass(frozen=True)
class FragilityCurve:
    """Lognormal fragility curve."""

    theta: float
    beta: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.theta <= 0.0 or self.beta <= 0.0:
            raise ValueError("theta and beta must be positive.")

    def probability(self, im: float | Sequence[float] | NDArray[np.float64]) -> NDArray[np.float64]:
        """Return exceedance probabilities for one or more IM values."""
        values = np.asarray(im, dtype=np.float64)
        if np.any(values <= 0.0):
            raise ValueError("im values must be positive.")

        def cdf(value: float) -> float:
            z = math.log(value / self.theta) / (self.beta * math.sqrt(2.0))
            return 0.5 * (1.0 + math.erf(z))

        return np.asarray(np.vectorize(cdf, otypes=[np.float64])(values), dtype=np.float64)


def cloud_fragility(
    psdm: Psdm,
    capacity: float,
    *,
    beta_capacity: float = 0.0,
    beta_modeling: float = 0.0,
    label: str = "",
) -> FragilityCurve:
    """Convert a PSDM and capacity into an IM-space fragility curve."""
    theta = psdm.median_im(capacity)
    beta = math.sqrt(psdm.beta**2 + beta_capacity**2 + beta_modeling**2) / abs(psdm.b)
    return FragilityCurve(theta=theta, beta=beta, label=label)


def ida_fragility(
    collapse_ims: Sequence[float] | NDArray[np.float64],
    *,
    label: str = "",
) -> FragilityCurve:
    """Fit a lognormal collapse fragility from IDA collapse intensities."""
    values = np.asarray(collapse_ims, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("at least two collapse IMs are required.")
    if np.any(values <= 0.0):
        raise ValueError("collapse IMs must be positive.")
    logs = np.log(values)
    return FragilityCurve(
        theta=float(np.exp(np.mean(logs))),
        beta=float(np.std(logs, ddof=1)),
        label=label,
    )


def msa_fragility(
    levels: Sequence[float] | NDArray[np.float64],
    n_total: Sequence[int] | NDArray[np.int_],
    n_exceed: Sequence[int] | NDArray[np.int_],
    *,
    label: str = "",
) -> FragilityCurve:
    """Fit Baker-style MSA fragility by binomial maximum likelihood."""
    optimize = require(
        "scipy.optimize",
        feature="MSA maximum-likelihood fragility fitting",
        extra="optimize",
    )
    levels_array = np.asarray(levels, dtype=np.float64)
    total = np.asarray(n_total, dtype=np.float64)
    exceed = np.asarray(n_exceed, dtype=np.float64)
    if (
        levels_array.shape != total.shape
        or total.shape != exceed.shape
        or levels_array.ndim != 1
    ):
        raise ValueError(
            "levels, n_total, and n_exceed must be one-dimensional arrays of equal length."
        )
    if (
        np.any(levels_array <= 0.0)
        or np.any(total <= 0.0)
        or np.any(exceed < 0.0)
        or np.any(exceed > total)
    ):
        raise ValueError(
            "levels must be positive and counts must satisfy 0 <= n_exceed <= n_total."
        )

    start = _msa_initial_guess(levels_array, total, exceed)

    def objective(params: NDArray[np.float64]) -> float:
        log_theta, log_beta = params
        theta = math.exp(float(log_theta))
        beta = math.exp(float(log_beta))
        z = np.log(levels_array / theta) / beta
        probs = np.vectorize(_normal_cdf, otypes=[np.float64])(z)
        probs = np.clip(probs, 1e-12, 1.0 - 1e-12)
        ll = exceed * np.log(probs) + (total - exceed) * np.log1p(-probs)
        return -float(np.sum(ll))

    result = optimize.minimize(
        objective,
        np.log(np.asarray(start, dtype=np.float64)),
        method="Nelder-Mead",
        options={"xatol": 1e-12, "fatol": 1e-12, "maxiter": 10000, "maxfev": 10000},
    )
    if not result.success:
        result = optimize.minimize(objective, result.x, method="BFGS")
    theta, beta = np.exp(result.x)
    return FragilityCurve(theta=float(theta), beta=float(beta), label=label)


def demands(
    results: Sequence[Any],
    *,
    edp: str,
    im: str,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Pull finished ``(IM, EDP)`` demand pairs from NLTH results."""
    im_values: list[float] = []
    edp_values: list[float] = []
    for result in results:
        if not result.finished:
            continue
        im_values.append(float(result.im[im]))
        edp_values.append(float(result.edp[edp]))
    return np.asarray(im_values, dtype=np.float64), np.asarray(edp_values, dtype=np.float64)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _msa_initial_guess(
    levels: NDArray[np.float64],
    total: NDArray[np.float64],
    exceed: NDArray[np.float64],
) -> tuple[float, float]:
    fractions = (exceed + 0.5) / (total + 1.0)
    order = np.argsort(levels)
    sorted_levels = levels[order]
    sorted_fractions = fractions[order]
    theta = float(sorted_levels[np.argmin(np.abs(sorted_fractions - 0.5))])
    beta = 0.4
    lower = sorted_levels[sorted_fractions >= 0.16]
    upper = sorted_levels[sorted_fractions >= 0.84]
    if lower.size and upper.size and upper[0] > lower[0]:
        beta = float(math.log(upper[0] / lower[0]) / 2.0)
    return max(theta, 1e-6), max(beta, 0.05)
