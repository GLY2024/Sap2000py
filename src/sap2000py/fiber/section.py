"""Fiber discretization of a cross-section for uniaxial bending analysis.

A :class:`FiberSection` is a collection of fibers, each with a centroidal
distance ``y`` from a reference axis, an ``area``, and a uniaxial material. The
section response under a strain plane ``epsilon(y) = eps0 + phi * y``
(tension-positive) is obtained by integrating fiber stresses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

from .materials import UniaxialMaterial


@dataclass
class FiberSection:
    """A set of fibers describing a cross-section (single bending axis)."""

    _ys: list[float] = field(default_factory=list)
    _areas: list[float] = field(default_factory=list)
    _materials: list[UniaxialMaterial] = field(default_factory=list)

    def add_fiber(self, y: float, area: float, material: UniaxialMaterial) -> None:
        """Add a single fiber at distance ``y`` with the given area and material."""
        if area <= 0:
            raise ValueError("fiber area must be positive.")
        self._ys.append(float(y))
        self._areas.append(float(area))
        self._materials.append(material)

    def add_rect_patch(
        self,
        material: UniaxialMaterial,
        *,
        y_min: float,
        y_max: float,
        width: float,
        n: int,
    ) -> None:
        """Discretize a rectangular region into ``n`` horizontal strips.

        The region spans ``y_min..y_max`` with the given ``width``; each strip
        is a fiber at its mid-height.
        """
        if n < 1:
            raise ValueError("n must be >= 1.")
        if y_max <= y_min or width <= 0:
            raise ValueError("require y_max > y_min and width > 0.")
        edges = np.linspace(y_min, y_max, n + 1)
        dy = (y_max - y_min) / n
        strip_area = width * dy
        for lo, hi in pairwise(edges):
            self.add_fiber(0.5 * (lo + hi), strip_area, material)

    def add_bars(self, material: UniaxialMaterial, ys: Sequence[float], area_each: float) -> None:
        """Add point-area reinforcing bars at the given ``y`` positions."""
        for y in ys:
            self.add_fiber(y, area_each, material)

    @property
    def y(self) -> NDArray[np.float64]:
        """Fiber distances from the reference axis."""
        return np.asarray(self._ys, dtype=float)

    @property
    def area(self) -> NDArray[np.float64]:
        """Fiber areas."""
        return np.asarray(self._areas, dtype=float)

    def __len__(self) -> int:
        return len(self._ys)

    def _fiber_stress(self, strain: NDArray[np.float64]) -> NDArray[np.float64]:
        """Stress in every fiber for the given per-fiber strain array.

        Materials are evaluated in groups (one vectorized call per distinct
        material object) for efficiency.
        """
        stress = np.empty_like(strain)
        groups: dict[int, list[int]] = {}
        for i, mat in enumerate(self._materials):
            groups.setdefault(id(mat), []).append(i)
        for indices in groups.values():
            mat = self._materials[indices[0]]
            idx = np.asarray(indices)
            stress[idx] = mat.stress(strain[idx])
        return stress

    def response(self, eps0: float, phi: float) -> tuple[float, float]:
        """Return ``(axial_force, moment)`` for a strain plane.

        ``epsilon(y) = eps0 + phi * y`` (tension-positive). Axial force is
        ``sum(area * stress)`` and moment is ``sum(area * stress * y)`` about the
        reference axis. Tension/positive-stress contributes positive axial force.
        """
        y = self.y
        strain = eps0 + phi * y
        stress = self._fiber_stress(strain)
        forces = self.area * stress
        return float(forces.sum()), float((forces * y).sum())

    def centroid(self) -> float:
        """Area-weighted centroid ``y`` of all fibers (geometric, gross area)."""
        area = self.area
        return float((area * self.y).sum() / area.sum())
