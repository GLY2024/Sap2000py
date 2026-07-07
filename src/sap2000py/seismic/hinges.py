"""Pure helpers for converting moment-curvature results into hinge inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from ..fiber import MomentCurvature
from ..model.hinges import MomentHinge


@dataclass(frozen=True)
class DamageStates:
    """Ordered damage-state thresholds in one EDP quantity."""

    quantity: Literal["curvature_ductility", "drift", "deformation"]
    thresholds: Mapping[str, float]

    def __post_init__(self) -> None:
        _validate_strictly_ascending(self.thresholds)


def hinge_from_mc(
    mc: MomentCurvature,
    *,
    name: str,
    hinge_length: float,
    ultimate_ratio: float = 1.0,
    residual: float = 0.2,
) -> MomentHinge:
    """Convert a bilinearized moment-curvature curve to a Moment-M3 hinge."""
    phi_y, m_y, phi_u, m_u = mc.bilinearize()
    if m_y == 0.0:
        raise ValueError("yield moment from bilinearize() cannot be zero.")
    theta_u = max((phi_u - phi_y) * float(hinge_length), 0.0)
    c_ratio = ultimate_ratio * (m_u / m_y)
    # ponytail: B..E only; the table adapter is responsible for symmetric export.
    backbone = (
        (0.0, 1.0),
        (theta_u, c_ratio),
        (theta_u, float(residual)),
        (1.25 * theta_u, float(residual)),
    )
    return MomentHinge(name=name, yield_moment=m_y, backbone=backbone)


def damage_states_from_mc(
    mc: MomentCurvature,
    *,
    mu: Sequence[float | None] = (1.0, 2.0, 4.0, None),
    names: Sequence[str] = ("slight", "moderate", "extensive", "complete"),
) -> DamageStates:
    """Create curvature-ductility damage-state thresholds from MC results."""
    if len(mu) != len(names):
        raise ValueError("mu and names must have the same length.")
    phi_y, _m_y, phi_u, _m_u = mc.bilinearize()
    if phi_y == 0.0:
        raise ValueError("yield curvature from bilinearize() cannot be zero.")
    mu_u = phi_u / phi_y
    thresholds = {
        name: float(mu_u if value is None else value)
        for name, value in zip(names, mu, strict=True)
    }
    if not _is_strictly_ascending(thresholds.values()):
        raise ValueError(
            "damage state thresholds must be strictly ascending; "
            f"thresholds={thresholds!r}; mu_u={mu_u!r}"
        )
    return DamageStates(quantity="curvature_ductility", thresholds=thresholds)


def _validate_strictly_ascending(thresholds: Mapping[str, float]) -> None:
    if not _is_strictly_ascending(thresholds.values()):
        raise ValueError(
            f"damage state thresholds must be strictly ascending: {dict(thresholds)!r}"
        )


def _is_strictly_ascending(values: Iterable[float]) -> bool:
    return all(b > a for a, b in pairwise(values))
