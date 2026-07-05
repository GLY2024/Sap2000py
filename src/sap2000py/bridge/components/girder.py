"""A continuous girder: a line of frame elements through deck nodes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...model.frame_sections import FrameSectionHandle
from ..component import BridgeComponent

if TYPE_CHECKING:
    from ...model import Model


class Girder(BridgeComponent):
    """A continuous girder through an ordered list of deck nodes.

    Nodes are created with ``merge=False`` so deck joints stay distinct from
    coincident bearing tops (which they connect to via a constraint).

    Anchors
    -------
    ``n0``, ``n1``, ...
        One per node, in order.
    ``start``, ``end``
        Aliases for the first and last nodes.
    """

    def __init__(
        self,
        name: str,
        nodes: Sequence[Sequence[float]],
        section: FrameSectionHandle | str,
    ) -> None:
        super().__init__(name)
        pts = [(float(x), float(y), float(z)) for x, y, z in nodes]
        if len(pts) < 2:
            raise ValueError(f"a girder needs at least 2 nodes, got {len(pts)}.")
        self.nodes = pts
        self.section = section

    def _build(self, model: Model) -> None:
        points = [
            model.points.add(x, y, z, name=f"{self.name}_n{i}", merge=False)
            for i, (x, y, z) in enumerate(self.nodes)
        ]
        for i in range(len(points) - 1):
            model.frames.add_by_points(
                points[i], points[i + 1], section=self.section, name=f"{self.name}_e{i}"
            )
        for i, point in enumerate(points):
            self._set_anchor(f"n{i}", point)
        self._set_anchor("start", points[0])
        self._set_anchor("end", points[-1])
