"""Frame (line) objects: create, section, releases, local axes, stations."""

from __future__ import annotations

from collections.abc import Sequence

from ..enums import ItemType
from ..handles import (
    FrameHandle,
    FrameSectionHandle,
    GroupHandle,
    PointHandle,
    as_name,
)
from ._base import Manager


class Frames(Manager):
    """Create and manipulate frame objects. Wraps ``cFrameObj``."""

    def _handle(self, name: str) -> FrameHandle:
        return FrameHandle(name, _owner=self)

    def add_by_points(
        self,
        i: PointHandle | str,
        j: PointHandle | str,
        *,
        section: FrameSectionHandle | str = "Default",
        name: str = "",
    ) -> FrameHandle:
        """Add a frame between two existing points. Wraps ``FrameObj.AddByPoint``."""
        assigned = self._g.call(
            self._raw.FrameObj.AddByPoint,
            as_name(i),
            as_name(j),
            "",
            as_name(section),
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
        assigned = self._g.call(
            self._raw.FrameObj.AddByCoord,
            float(xi),
            float(yi),
            float(zi),
            float(xj),
            float(yj),
            float(zj),
            "",
            as_name(section),
            name,
            csys,
            api_name="FrameObj.AddByCoord",
        )
        return self._handle(assigned)

    def set_section(
        self,
        frame: FrameHandle | str,
        section: FrameSectionHandle | str,
        *,
        item_type: ItemType = ItemType.OBJECT,
    ) -> None:
        """Assign a section property to a frame. Wraps ``FrameObj.SetSection``."""
        self._g.call(
            self._raw.FrameObj.SetSection,
            as_name(frame),
            as_name(section),
            int(item_type),
            api_name="FrameObj.SetSection",
        )

    def set_releases(
        self,
        frame: FrameHandle | str,
        *,
        i_end: Sequence[bool],
        j_end: Sequence[bool],
        item_type: ItemType = ItemType.OBJECT,
    ) -> None:
        """Release DOF at the frame ends (no partial fixity).

        ``i_end``/``j_end`` are 6-element ``[U1..R3]`` masks; ``True`` releases
        that DOF. Wraps ``FrameObj.SetReleases``.
        """
        if len(i_end) != 6 or len(j_end) != 6:
            raise ValueError("i_end and j_end must each have 6 elements [U1..R3].")
        zeros = [0.0] * 6
        self._g.call(
            self._raw.FrameObj.SetReleases,
            as_name(frame),
            list(i_end),
            list(j_end),
            zeros,
            zeros,
            int(item_type),
            api_name="FrameObj.SetReleases",
        )

    def set_local_axes(
        self,
        frame: FrameHandle | str,
        angle: float,
        *,
        item_type: ItemType = ItemType.OBJECT,
    ) -> None:
        """Set the local-axis rotation angle (degrees). Wraps ``FrameObj.SetLocalAxes``."""
        self._g.call(
            self._raw.FrameObj.SetLocalAxes,
            as_name(frame),
            float(angle),
            int(item_type),
            api_name="FrameObj.SetLocalAxes",
        )

    def set_output_stations(
        self,
        frame: FrameHandle | str,
        *,
        min_stations: int | None = None,
        max_segment_size: float | None = None,
        item_type: ItemType = ItemType.OBJECT,
    ) -> None:
        """Set output stations by count or by max segment size.

        Provide exactly one of ``min_stations`` or ``max_segment_size``. Wraps
        ``FrameObj.SetOutputStations`` (myType 1 = max size, 2 = min number).
        """
        if (min_stations is None) == (max_segment_size is None):
            raise ValueError("provide exactly one of min_stations or max_segment_size.")
        if min_stations is not None:
            my_type, max_seg, min_sec = 2, 0.0, int(min_stations)
        else:
            my_type, max_seg, min_sec = 1, float(max_segment_size), 2  # type: ignore[arg-type]
        # SetOutputStations(Name, MyType, MaxSegSize, MinSections, NoOutAtEnds,
        #                   NoOutAtPointLoads, ItemType)
        self._g.call(
            self._raw.FrameObj.SetOutputStations,
            as_name(frame),
            my_type,
            max_seg,
            min_sec,
            False,
            False,
            int(item_type),
            api_name="FrameObj.SetOutputStations",
        )

    def add_to_group(
        self,
        frame: FrameHandle | str,
        group: GroupHandle | str,
        *,
        remove: bool = False,
        item_type: ItemType = ItemType.OBJECT,
    ) -> None:
        """Add (or remove) a frame from a group. Wraps ``FrameObj.SetGroupAssign``."""
        self._g.call(
            self._raw.FrameObj.SetGroupAssign,
            as_name(frame),
            as_name(group),
            remove,
            int(item_type),
            api_name="FrameObj.SetGroupAssign",
        )

    def count(self) -> int:
        """Number of frame objects. Wraps ``FrameObj.Count``."""
        return int(self._g.value(self._raw.FrameObj.Count, api_name="FrameObj.Count"))

    def names(self) -> list[str]:
        """All frame object names. Wraps ``FrameObj.GetNameList``."""
        _count, names = self._g.call(
            self._raw.FrameObj.GetNameList, api_name="FrameObj.GetNameList"
        )
        return list(names) if names else []
