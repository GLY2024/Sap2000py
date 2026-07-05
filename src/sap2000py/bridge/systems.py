"""System assemblers: lay out and connect components into a whole bridge."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..errors import MissingDependencyError
from ..model.frame_sections import FrameSectionHandle
from .components.bearing import Bearing
from .components.foundation import Foundation
from .components.girder import Girder
from .components.pier import Pier
from .connect import Connection, snap_connect

if TYPE_CHECKING:
    from ..model import Model


@dataclass(frozen=True)
class BridgeBuild:
    """What a :meth:`ContinuousGirderBridge.build` produced, for inspection."""

    foundations: list[Foundation]
    piers: list[Pier]
    bearings: list[Bearing]
    girder: Girder
    connections: list[str]


class ContinuousGirderBridge:
    """A multi-span continuous girder on bearings, piers and foundations.

    Supports sit at the cumulative span stations along global X. Each support is
    a foundation → pier → bearing stack; one girder runs across all the bearing
    tops. :meth:`build` creates every component in a model and rigidly connects
    each interface with :func:`~sap2000py.bridge.connect.snap_connect`.

    The frame sections must already exist in the model (define them with
    ``model.materials`` / ``model.frame_sections`` first); this assembler owns
    geometry and topology, not material definition.
    """

    def __init__(
        self,
        name: str,
        *,
        spans: Sequence[float],
        pier_height: float,
        girder_section: FrameSectionHandle | str,
        pier_section: FrameSectionHandle | str,
        bearing_stiffness: Sequence[float],
        bearing_height: float = 0.0,
        pier_segments: int = 1,
        foundation: Literal["fixed", "spring"] = "fixed",
        foundation_stiffness: Sequence[float] | None = None,
        origin: Sequence[float] = (0.0, 0.0, 0.0),
    ) -> None:
        if len(spans) < 1:
            raise ValueError("a continuous girder needs at least one span.")
        if any(length <= 0 for length in spans):
            raise ValueError("span lengths must be positive.")
        self.name = name
        self.spans = [float(length) for length in spans]
        self.pier_height = float(pier_height)
        self.girder_section = girder_section
        self.pier_section = pier_section
        self.bearing_stiffness = bearing_stiffness
        self.bearing_height = float(bearing_height)
        self.pier_segments = int(pier_segments)
        self.foundation = foundation
        self.foundation_stiffness = foundation_stiffness
        self.origin = (float(origin[0]), float(origin[1]), float(origin[2]))

    @property
    def support_x(self) -> list[float]:
        """Global X of each support (one more than the number of spans)."""
        x0 = self.origin[0]
        return [x0, *(x0 + s for s in accumulate(self.spans))]

    @classmethod
    def from_yaml(cls, path: str | Path) -> ContinuousGirderBridge:
        """Build a bridge spec from a YAML file (needs the ``bridge`` extra).

        Keys mirror the constructor; ``name`` defaults to the file stem.
        """
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - exercised without the extra
            raise MissingDependencyError("bridge YAML configs", "bridge") from exc
        path = Path(path)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.setdefault("name", path.stem)
        return cls(data.pop("name"), **data)

    def build(self, model: Model) -> BridgeBuild:
        """Create and connect every component; return the built pieces."""
        _, y0, z0 = self.origin
        deck_z = z0 + self.pier_height + self.bearing_height

        foundations: list[Foundation] = []
        piers: list[Pier] = []
        bearings: list[Bearing] = []
        deck_nodes: list[tuple[float, float, float]] = []

        for i, x in enumerate(self.support_x):
            foundation = Foundation(
                f"{self.name}_F{i}",
                x,
                y0,
                z0,
                kind=self.foundation,
                stiffness=self.foundation_stiffness,
            )
            pier = Pier(
                f"{self.name}_P{i}",
                (x, y0, z0),
                self.pier_height,
                self.pier_section,
                segments=self.pier_segments,
            )
            bearing = Bearing(
                f"{self.name}_B{i}",
                x,
                y0,
                z0 + self.pier_height,
                stiffness=self.bearing_stiffness,
                height=self.bearing_height,
            )
            for component in (foundation, pier, bearing):
                component.build(model)
            foundations.append(foundation)
            piers.append(pier)
            bearings.append(bearing)
            deck_nodes.append((x, y0, deck_z))

        girder = Girder(f"{self.name}_girder", deck_nodes, self.girder_section)
        girder.build(model)

        connections: list[str] = []
        for i, (foundation, pier, bearing) in enumerate(
            zip(foundations, piers, bearings, strict=True)
        ):
            connections.append(
                snap_connect(
                    model,
                    foundation.anchor("top"),
                    pier.anchor("bottom"),
                    how=Connection.BODY,
                    name=f"{self.name}_FP{i}",
                )
            )
            connections.append(
                snap_connect(
                    model,
                    pier.anchor("top"),
                    bearing.anchor("bottom"),
                    how=Connection.BODY,
                    name=f"{self.name}_PB{i}",
                )
            )
            connections.append(
                snap_connect(
                    model,
                    bearing.anchor("top"),
                    girder.anchor(f"n{i}"),
                    how=Connection.BODY,
                    name=f"{self.name}_BG{i}",
                )
            )

        return BridgeBuild(foundations, piers, bearings, girder, connections)
