"""Pier-base support: a fixed restraint or a 6-DOF elastic spring."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from ...enums import DOF
from ..component import BridgeComponent

if TYPE_CHECKING:
    from ...model import Model


class Foundation(BridgeComponent):
    """A pier base support.

    ``kind="fixed"`` fully restrains the base; ``kind="spring"`` applies six
    uncoupled spring stiffnesses (an elastic-foundation idealization).

    Anchors
    -------
    ``top``
        The base joint a pier connects to.
    """

    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        z: float = 0.0,
        *,
        kind: Literal["fixed", "spring"] = "fixed",
        stiffness: Sequence[float] | None = None,
        fix_dof: Sequence[bool] | None = None,
    ) -> None:
        super().__init__(name)
        if kind not in ("fixed", "spring"):
            raise ValueError(f"kind must be 'fixed' or 'spring', got {kind!r}.")
        if kind == "spring" and stiffness is None:
            raise ValueError("a spring foundation needs stiffness=[U1..R3].")
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.kind = kind
        self.stiffness = stiffness
        self.fix_dof = fix_dof

    def _build(self, model: Model) -> None:
        base = model.points.add(self.x, self.y, self.z, name=f"{self.name}_base", merge=False)
        if self.kind == "fixed":
            model.points.set_restraints(base, self.fix_dof or DOF.fixed())
        else:
            assert self.stiffness is not None  # guarded in __init__
            model.points.set_spring(base, self.stiffness)
        self._set_anchor("top", base)
