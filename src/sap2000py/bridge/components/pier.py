"""A single-column pier, discretized from base to top."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...model.frame_sections import FrameSectionHandle
from ..component import BridgeComponent

if TYPE_CHECKING:
    from ...model import Model


class Pier(BridgeComponent):
    """A vertical single-column pier from ``base`` up by ``height``.

    The column is split into ``segments`` frame elements (more segments → finer
    mode shapes and load distribution).

    Anchors
    -------
    ``bottom``
        The base joint (connect to a :class:`~sap2000py.bridge.components.foundation.Foundation`).
    ``top``
        The cap-level joint (connect to a bearing).
    """

    def __init__(
        self,
        name: str,
        base: Sequence[float],
        height: float,
        section: FrameSectionHandle | str,
        *,
        segments: int = 1,
    ) -> None:
        super().__init__(name)
        if len(base) != 3:
            raise ValueError(f"base must be (x, y, z), got {base!r}.")
        if height <= 0:
            raise ValueError(f"height must be positive, got {height}.")
        if segments < 1:
            raise ValueError(f"segments must be >= 1, got {segments}.")
        self.base = (float(base[0]), float(base[1]), float(base[2]))
        self.height = float(height)
        self.section = section
        self.segments = int(segments)

    def _build(self, model: Model) -> None:
        x, y, z0 = self.base
        points = [
            model.points.add(
                x, y, z0 + self.height * i / self.segments, name=f"{self.name}_p{i}", merge=False
            )
            for i in range(self.segments + 1)
        ]
        for i in range(self.segments):
            model.frames.add_by_points(
                points[i], points[i + 1], section=self.section, name=f"{self.name}_e{i}"
            )
        self._set_anchor("bottom", points[0])
        self._set_anchor("top", points[-1])
