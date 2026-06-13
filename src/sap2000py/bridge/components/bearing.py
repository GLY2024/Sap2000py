"""A bridge bearing, modelled as a linear two-joint link."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..component import BridgeComponent

if TYPE_CHECKING:
    from ...model import Model


class Bearing(BridgeComponent):
    """An elastomeric/pot bearing as a linear link with six DOF stiffnesses.

    Builds a bottom and a top joint ``height`` apart (``height=0`` gives the
    common zero-length link), a linear link property, and the link between them.
    The two joints are kept distinct (``merge=False``) so a zero-height bearing
    is still two nodes, not one.

    Anchors
    -------
    ``bottom``
        Rests on the pier/cap.
    ``top``
        Carries the girder.
    """

    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        z: float,
        *,
        stiffness: Sequence[float],
        height: float = 0.0,
    ) -> None:
        super().__init__(name)
        if len(stiffness) != 6:
            raise ValueError(f"stiffness must have 6 elements [U1..R3], got {len(stiffness)}.")
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.stiffness = stiffness
        self.height = float(height)

    def _build(self, model: Model) -> None:
        bottom = model.points.add(self.x, self.y, self.z, name=f"{self.name}_b", merge=False)
        top = model.points.add(
            self.x, self.y, self.z + self.height, name=f"{self.name}_t", merge=False
        )
        prop = model.link_props.add_linear(f"{self.name}_prop", self.stiffness)
        model.links.add_by_points(bottom, top, prop, name=self.name)
        self._set_anchor("bottom", bottom)
        self._set_anchor("top", top)
