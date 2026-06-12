"""Axial-moment (P-M) interaction surfaces from a fiber section.

The interaction envelope is traced by imposing linear ultimate strain profiles
on a :class:`~sap2000py.fiber.section.FiberSection`: the extreme compression
fiber is pinned at the concrete crushing strain while the opposite fiber sweeps
from the same compression (pure axial) through to a large tension (steel
rupture). Each profile yields one ``(axial, moment)`` point on the envelope.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..fiber.section import FiberSection


@dataclass(frozen=True)
class PMInteraction:
    """A P-M interaction envelope (tension-positive axial)."""

    axial: NDArray[np.float64]
    moment: NDArray[np.float64]

    @property
    def max_moment(self) -> float:
        """Peak moment on the envelope (the balanced-ish point)."""
        return float(np.max(self.moment))

    @property
    def squash_load(self) -> float:
        """Most compressive axial capacity (most negative axial)."""
        return float(np.min(self.axial))


def pm_interaction(
    section: FiberSection,
    *,
    eps_cu: float,
    eps_tension: float = 0.05,
    n_points: int = 40,
) -> PMInteraction:
    """Trace the positive-bending P-M interaction envelope of a fiber section.

    Parameters
    ----------
    section:
        The fiber section.
    eps_cu:
        Ultimate compressive strain (magnitude) pinned at the extreme
        compression fiber.
    eps_tension:
        Largest tensile strain swept at the opposite extreme fiber (e.g. steel
        rupture). Defaults to 0.05.
    n_points:
        Number of strain profiles swept from pure compression to full tension.

    Returns
    -------
    PMInteraction
        The envelope as paired axial/moment arrays. Axial is tension-positive,
        so compression capacities are negative.
    """
    y = section.y
    if len(y) == 0:
        raise ValueError("section has no fibers.")
    y_bot, y_top = float(y.min()), float(y.max())
    depth = y_top - y_bot
    if depth <= 0:
        raise ValueError("section fibers must span a non-zero depth.")

    # Pin the bottom fiber at crushing; sweep the top fiber from -eps_cu
    # (uniform compression) up to +eps_tension (extreme tension).
    eps_top_values = np.linspace(-eps_cu, eps_tension, n_points)
    axial = np.empty(n_points)
    moment = np.empty(n_points)
    for i, eps_top in enumerate(eps_top_values):
        phi = (eps_top - (-eps_cu)) / depth
        eps0 = -eps_cu - phi * y_bot  # eps(y_bot) == -eps_cu
        axial[i], moment[i] = section.response(eps0, float(phi))
    return PMInteraction(axial=axial, moment=moment)
