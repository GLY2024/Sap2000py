"""Link (two-joint) elements: bearings, isolators, dampers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..handles import Handle
from ._base import Manager
from .link_props import LinkPropHandle
from .points import PointHandle


@dataclass(frozen=True)
class LinkHandle(Handle):
    """A live link object reference."""

    _manager_path: ClassVar[str] = "m.links"

    def delete(self) -> None:
        """Delete this link object."""
        owner = self._require_owner()
        owner._g.call(owner._raw.LinkObj.Delete, self.name, api_name="LinkObj.Delete")


class Links(Manager[LinkHandle]):
    """Create and query link objects. Wraps ``cLinkObj``."""

    _handle_cls = LinkHandle
    _kind = "link"

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
        point_i_ref = self._model.points.ref(point_i)
        point_j_ref = self._model.points.ref(point_j)
        prop_ref = self._model.link_props.ref(prop)
        assigned = self._g.call(
            self._raw.LinkObj.AddByPoint,
            point_i_ref.name,
            point_j_ref.name,
            "",
            single_joint,
            prop_ref.name,
            name,
            api_name="LinkObj.AddByPoint",
        )
        return self._handle(assigned)

    def count(self) -> int:
        """Number of link objects. Wraps ``LinkObj.Count``."""
        return int(self._g.value(self._raw.LinkObj.Count, api_name="LinkObj.Count"))

    def names(self) -> list[str]:
        """All link object names. Wraps ``LinkObj.GetNameList``."""
        _count, names = self._g.call(self._raw.LinkObj.GetNameList, api_name="LinkObj.GetNameList")
        return list(names) if names else []
