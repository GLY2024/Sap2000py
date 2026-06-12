"""Uniaxial constitutive models for fiber section analysis.

Sign convention throughout: **tension-positive** for both strain and stress.
Concrete therefore carries load only at negative (compressive) strain and
returns negative (compressive) stress; steel is symmetric.

All ``stress`` methods are vectorized: they accept a float or a NumPy array and
return the same shape.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray


@runtime_checkable
class UniaxialMaterial(Protocol):
    """A uniaxial stress-strain law (tension-positive)."""

    def stress(self, strain: ArrayLike) -> NDArray[np.float64]:
        """Return stress for the given strain (float or array)."""
        ...


class BilinearSteel:
    """Elastic-plastic steel with linear strain hardening.

    Parameters
    ----------
    E:
        Elastic modulus.
    fy:
        Yield stress.
    hardening:
        Post-yield stiffness as a fraction of ``E`` (default 1%).
    eps_ult:
        Optional rupture strain; beyond ``|strain| > eps_ult`` the stress drops
        to zero.
    """

    def __init__(
        self, E: float, fy: float, *, hardening: float = 0.01, eps_ult: float | None = None
    ) -> None:
        if E <= 0 or fy <= 0:
            raise ValueError("E and fy must be positive.")
        self.E = float(E)
        self.fy = float(fy)
        self.hardening = float(hardening)
        self.eps_ult = eps_ult
        self.eps_y = self.fy / self.E

    def stress(self, strain: ArrayLike) -> NDArray[np.float64]:
        e = np.asarray(strain, dtype=float)
        sign = np.sign(e)
        backbone = np.where(
            np.abs(e) <= self.eps_y,
            self.E * e,
            sign * self.fy + self.hardening * self.E * (e - sign * self.eps_y),
        )
        if self.eps_ult is not None:
            backbone = np.where(np.abs(e) > self.eps_ult, 0.0, backbone)
        return np.asarray(backbone, dtype=float)


class ManderConcrete:
    """Mander, Priestley & Park (1988) concrete model (compression only).

    Works for both unconfined (``fcc == fco``) and confined (``fcc > fco``)
    concrete via the same envelope. Tension is ignored.

    Parameters
    ----------
    fco:
        Unconfined compressive strength (magnitude, positive).
    Ec:
        Concrete elastic modulus. If omitted, ``5000 * sqrt(fco)`` is used,
        which assumes ``fco`` is expressed in **MPa**.
    fcc:
        Confined peak strength (magnitude). Defaults to ``fco`` (unconfined).
    eps_co:
        Strain at unconfined peak stress (default 0.002).
    eps_cu:
        Ultimate (crushing) compressive strain magnitude. Beyond it the stress
        is zero. Defaults to 0.004 unconfined, scaled up when confined.
    """

    def __init__(
        self,
        fco: float,
        *,
        Ec: float | None = None,
        fcc: float | None = None,
        eps_co: float = 0.002,
        eps_cu: float | None = None,
    ) -> None:
        if fco <= 0:
            raise ValueError("fco must be positive.")
        self.fco = float(fco)
        self.fcc = float(fcc) if fcc is not None else float(fco)
        self.eps_co = float(eps_co)
        self.Ec = float(Ec) if Ec is not None else 5000.0 * math.sqrt(self.fco)
        # Strain at confined peak stress (Mander eq.).
        self.eps_cc = self.eps_co * (1.0 + 5.0 * (self.fcc / self.fco - 1.0))
        if eps_cu is not None:
            self.eps_cu = float(eps_cu)
        else:
            confinement = self.fcc / self.fco
            self.eps_cu = 0.004 * confinement if confinement > 1.0 else 0.004
        esec = self.fcc / self.eps_cc
        if self.Ec <= esec:
            raise ValueError("Ec must exceed the secant modulus fcc/eps_cc.")
        self._r = self.Ec / (self.Ec - esec)

    def stress(self, strain: ArrayLike) -> NDArray[np.float64]:
        e = np.asarray(strain, dtype=float)
        # Compression magnitude (positive where strain is negative).
        ec = np.clip(-e, 0.0, None)
        x = ec / self.eps_cc
        denom = self._r - 1.0 + np.power(x, self._r)
        fc = self.fcc * x * self._r / denom
        fc = np.where(ec <= 0.0, 0.0, fc)
        fc = np.where(ec > self.eps_cu, 0.0, fc)
        return np.asarray(-fc, dtype=float)  # compression is negative stress


class LinearElastic:
    """A trivial linear-elastic uniaxial material (useful for tests/elastic checks)."""

    def __init__(self, E: float) -> None:
        if E <= 0:
            raise ValueError("E must be positive.")
        self.E = float(E)

    def stress(self, strain: ArrayLike) -> NDArray[np.float64]:
        return np.asarray(self.E * np.asarray(strain, dtype=float), dtype=float)
