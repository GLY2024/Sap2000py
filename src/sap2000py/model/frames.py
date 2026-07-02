"""Frame (line) objects: create, section, releases, local axes, stations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import dist
from typing import Any, ClassVar

from ..enums import ItemType, to_dof_mask
from ..handles import Handle
from ._base import Manager
from ._compat import frame_output_stations_args
from .frame_sections import FrameSectionHandle
from .groups import GroupHandle
from .points import PointHandle

DofSpec = str | Sequence[str] | Sequence[bool] | None


@dataclass(frozen=True)
class FrameHandle(Handle):
    """A live frame object reference."""

    _manager_path: ClassVar[str] = "m.frames"

    def release(self, *, i_end: DofSpec = None, j_end: DofSpec = None) -> FrameHandle:
        """Write the complete release state at both ends and return ``self``.

        Omitted ends are written as fully unreleased, so this overwrites any
        previous release state rather than preserving it.
        """
        owner = self._require_owner()
        zeros = [0.0] * 6
        owner._g.call(
            owner._raw.FrameObj.SetReleases,
            self.name,
            to_dof_mask(i_end, default=False),
            to_dof_mask(j_end, default=False),
            zeros,
            zeros,
            int(ItemType.OBJECT),
            api_name="FrameObj.SetReleases",
        )
        return self

    def assign_section(self, section: FrameSectionHandle | str) -> FrameHandle:
        """Assign a frame section and return ``self``."""
        owner = self._require_owner()
        section_ref = owner._model.frame_sections.ref(section)
        owner._g.call(
            owner._raw.FrameObj.SetSection,
            self.name,
            section_ref.name,
            int(ItemType.OBJECT),
            api_name="FrameObj.SetSection",
        )
        return self

    def rotate(self, angle: float) -> FrameHandle:
        """Set the local-axis rotation angle in degrees and return ``self``."""
        owner = self._require_owner()
        owner._g.call(
            owner._raw.FrameObj.SetLocalAxes,
            self.name,
            float(angle),
            int(ItemType.OBJECT),
            api_name="FrameObj.SetLocalAxes",
        )
        return self

    def set_output_stations(
        self,
        *,
        min_stations: int | None = None,
        max_segment_size: float | None = None,
    ) -> FrameHandle:
        """Set output stations by count or by max segment size and return ``self``."""
        if (min_stations is None) == (max_segment_size is None):
            raise ValueError("provide exactly one of min_stations or max_segment_size.")
        if min_stations is not None:
            my_type, max_seg, min_sec = 2, 0.0, int(min_stations)
        else:
            my_type, max_seg, min_sec = 1, float(max_segment_size), 2  # type: ignore[arg-type]
        owner = self._require_owner()
        args = frame_output_stations_args(
            owner._model.sap_version_major,
            my_type=my_type,
            max_seg=max_seg,
            min_sec=min_sec,
            no_ends=False,
            no_ptloads=False,
            item_type=int(ItemType.OBJECT),
        )
        owner._g.call(
            owner._raw.FrameObj.SetOutputStations,
            self.name,
            *args,
            api_name="FrameObj.SetOutputStations",
        )
        return self

    def group(self, group: GroupHandle | str, *, remove: bool = False) -> FrameHandle:
        """Add or remove this frame from a group and return ``self``."""
        owner = self._require_owner()
        group_ref = owner._model.groups.ref(group)
        owner._g.call(
            owner._raw.FrameObj.SetGroupAssign,
            self.name,
            group_ref.name,
            remove,
            int(ItemType.OBJECT),
            api_name="FrameObj.SetGroupAssign",
        )
        return self

    @property
    def length(self) -> float:
        """Straight-line end-to-end length in the current model length unit.

        Each access queries SAP2000 for the frame endpoints and point
        coordinates; the value is not cached.
        """
        owner = self._require_owner()
        i_name, j_name = owner._g.call(
            owner._raw.FrameObj.GetPoints,
            self.name,
            "",
            "",
            api_name="FrameObj.GetPoints",
        )
        i = owner._model.points.ref(i_name).coordinates()
        j = owner._model.points.ref(j_name).coordinates()
        return float(dist(i, j))

    def forces(self) -> Any:
        """Frame forces for the currently selected output cases/combos."""
        owner = self._require_owner()
        return owner._model.results.frame_forces(self)

    def delete(self) -> None:
        """Delete this frame object."""
        owner = self._require_owner()
        owner._g.call(
            owner._raw.FrameObj.Delete,
            self.name,
            int(ItemType.OBJECT),
            api_name="FrameObj.Delete",
        )


class Frames(Manager[FrameHandle]):
    """Create and manipulate frame objects. Wraps ``cFrameObj``."""

    _handle_cls = FrameHandle
    _kind = "frame"

    def add_by_points(
        self,
        i: PointHandle | str,
        j: PointHandle | str,
        *,
        section: FrameSectionHandle | str = "Default",
        name: str = "",
    ) -> FrameHandle:
        """Add a frame between two existing points. Wraps ``FrameObj.AddByPoint``."""
        i_ref = self._model.points.ref(i)
        j_ref = self._model.points.ref(j)
        section_ref = self._model.frame_sections.ref(section)
        assigned = self._g.call(
            self._raw.FrameObj.AddByPoint,
            i_ref.name,
            j_ref.name,
            "",
            section_ref.name,
            name,
            api_name="FrameObj.AddByPoint",
        )
        return self._handle(assigned)

    def add_by_coord(
        self,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
        *,
        section: FrameSectionHandle | str = "Default",
        name: str = "",
        csys: str = "Global",
    ) -> FrameHandle:
        """Add a frame between two coordinates. Wraps ``FrameObj.AddByCoord``."""
        xi, yi, zi = start
        xj, yj, zj = end
        section_ref = self._model.frame_sections.ref(section)
        assigned = self._g.call(
            self._raw.FrameObj.AddByCoord,
            float(xi),
            float(yi),
            float(zi),
            float(xj),
            float(yj),
            float(zj),
            "",
            section_ref.name,
            name,
            csys,
            api_name="FrameObj.AddByCoord",
        )
        return self._handle(assigned)

    def count(self) -> int:
        """Number of frame objects. Wraps ``FrameObj.Count``."""
        return int(self._g.value(self._raw.FrameObj.Count, api_name="FrameObj.Count"))

    def names(self) -> list[str]:
        """All frame object names. Wraps ``FrameObj.GetNameList``."""
        _count, names = self._g.call(
            self._raw.FrameObj.GetNameList, api_name="FrameObj.GetNameList"
        )
        return list(names) if names else []
