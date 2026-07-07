"""Numeric tests for seismic fragility utilities."""

from __future__ import annotations

import math

import numpy as np
import pytest

from sap2000py.seismic.fragility import (
    FragilityCurve,
    Psdm,
    cloud_fragility,
    fit_psdm,
    ida_fragility,
    msa_fragility,
)


def test_fit_psdm_recovers_ln_linear_model_and_residual_beta() -> None:
    ln_a = math.log(0.03)
    b = 1.35
    target_beta = 0.22
    x = np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0], dtype=np.float64)
    residual_shape = np.asarray([1.0, -2.0, 2.0, -2.0, 1.0], dtype=np.float64)
    residual = residual_shape * target_beta * math.sqrt(3.0 / 14.0)
    im = np.exp(x)
    edp = np.exp(ln_a + b * x + residual)
    psdm = fit_psdm(im, edp)
    assert psdm.ln_a == pytest.approx(ln_a)
    assert psdm.b == pytest.approx(b)
    assert psdm.beta == pytest.approx(target_beta)


def test_fragility_probability_matches_erf_values() -> None:
    curve = FragilityCurve(theta=0.7, beta=0.4)
    assert float(curve.probability(0.7)) == pytest.approx(0.5)
    assert float(curve.probability(0.7 * math.exp(0.4))) == pytest.approx(0.8413447461)
    assert float(curve.probability(0.7 * math.exp(-0.4))) == pytest.approx(0.1586552539)


def test_cloud_fragility_uses_im_space_dispersion() -> None:
    psdm = Psdm(ln_a=math.log(0.02), b=1.5, beta=0.3)
    curve = cloud_fragility(psdm, 0.08, beta_capacity=0.2, beta_modeling=0.1)
    assert curve.theta == pytest.approx(math.exp((math.log(0.08) - math.log(0.02)) / 1.5))
    assert curve.beta == pytest.approx(math.sqrt(0.3**2 + 0.2**2 + 0.1**2) / 1.5)


def test_ida_fragility_recovers_lognormal_sample_parameters() -> None:
    theta = 0.9
    beta = 0.35
    z = np.asarray([-1.0, 0.0, 1.0], dtype=np.float64)
    curve = ida_fragility(theta * np.exp(beta * z))
    assert curve.theta == pytest.approx(theta)
    assert curve.beta == pytest.approx(beta)


def test_msa_fragility_matches_stripe_mle() -> None:
    pytest.importorskip("scipy.optimize")
    levels = np.asarray([0.2, 0.4, 0.6, 0.8, 1.0, 1.2], dtype=np.float64)
    n_total = np.asarray([40, 40, 40, 40, 40, 40])
    n_exceed = np.asarray([0, 3, 11, 23, 32, 38])
    theta_ref, beta_ref = _reference_msa_mle(levels, n_total, n_exceed)
    curve = msa_fragility(levels, n_total, n_exceed)
    assert curve.theta == pytest.approx(theta_ref, rel=1e-4)
    assert curve.beta == pytest.approx(beta_ref, rel=1e-4)


def _reference_msa_mle(
    levels: np.ndarray,
    n_total: np.ndarray,
    n_exceed: np.ndarray,
) -> tuple[float, float]:
    theta = 0.8
    beta = 0.35
    theta_span = 0.4
    beta_span = 0.4
    for _ in range(12):
        theta_values = np.linspace(
            max(1e-6, theta - theta_span / 2.0),
            theta + theta_span / 2.0,
            2001,
        )
        theta_scores = _msa_log_likelihood_theta(
            theta_values,
            beta,
            levels,
            n_total,
            n_exceed,
        )
        theta = float(theta_values[np.argmax(theta_scores)])
        beta_values = np.linspace(
            max(1e-6, beta - beta_span / 2.0),
            beta + beta_span / 2.0,
            2001,
        )
        beta_scores = _msa_log_likelihood_beta(
            theta,
            beta_values,
            levels,
            n_total,
            n_exceed,
        )
        beta = float(beta_values[np.argmax(beta_scores)])
        theta_span /= 5.0
        beta_span /= 5.0
    return theta, beta


def _msa_log_likelihood_theta(
    theta: np.ndarray,
    beta: float,
    levels: np.ndarray,
    n_total: np.ndarray,
    n_exceed: np.ndarray,
) -> np.ndarray:
    z = np.log(levels[:, None] / theta[None, :]) / beta
    probabilities = np.clip(_normal_cdf_array(z), 1e-15, 1.0 - 1e-15)
    return np.sum(
        n_exceed[:, None] * np.log(probabilities)
        + (n_total - n_exceed)[:, None] * np.log1p(-probabilities),
        axis=0,
    )


def _msa_log_likelihood_beta(
    theta: float,
    beta: np.ndarray,
    levels: np.ndarray,
    n_total: np.ndarray,
    n_exceed: np.ndarray,
) -> np.ndarray:
    z = np.log(levels[:, None] / theta) / beta[None, :]
    probabilities = np.clip(_normal_cdf_array(z), 1e-15, 1.0 - 1e-15)
    return np.sum(
        n_exceed[:, None] * np.log(probabilities)
        + (n_total - n_exceed)[:, None] * np.log1p(-probabilities),
        axis=0,
    )


def _normal_cdf_array(values: np.ndarray) -> np.ndarray:
    flat = np.ravel(values)
    probabilities = [
        0.5 * (1.0 + math.erf(float(value) / math.sqrt(2.0)))
        for value in flat
    ]
    return np.asarray(probabilities, dtype=np.float64).reshape(values.shape)
