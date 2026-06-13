"""Link (two-joint) elements: bearings, isolators, dampers."""

from __future__ import annotations

from ..handles import LinkHandle, LinkPropHandle, PointHandle, as_name
from ._base import Manager


class Links(Manager):
    """Create and query link objects. Wraps ``cLinkObj``."""

    def add_by_points(
        self,
        point_i: PointHandle | str,
        point_j: PointHandle | str,
        prop: LinkPropHandle | str,
        *,
        name: str = "",
        single_joint: bool = False,
    ) -> LinkHandle:
        """Add a link between two points referencing ``prop``.

        Wraps ``LinkObj.AddByPoint``. Returns the assigned link (the name
        SAP2000 chose if ``name`` was blank or taken).
        """
        # AddByPoint(Point1, Point2, Name[in,out], IsSingleJoint, PropName, UserName)
        assigned = self._g.call(
            self._raw.LinkObj.AddByPoint,
            as_name(point_i),
            as_name(point_j),
            "",
            single_joint,
            as_name(prop),
            name,
            api_name="LinkObj.AddByPoint",
        )
        return LinkHandle(assigned, _owner=self)

    def count(self) -> int:
        """Number of link objects. Wraps ``LinkObj.Count``."""
        return int(self._g.value(self._raw.LinkObj.Count, api_name="LinkObj.Count"))

    def names(self) -> list[str]:
        """All link object names. Wraps ``LinkObj.GetNameList``."""
        _count, names = self._g.call(self._raw.LinkObj.GetNameList, api_name="LinkObj.GetNameList")
        return list(names) if names else []

    def delete(self, link: LinkHandle | str) -> None:
        """Delete a link object. Wraps ``LinkObj.Delete``."""
        self._g.call(self._raw.LinkObj.Delete, as_name(link), api_name="LinkObj.Delete")
