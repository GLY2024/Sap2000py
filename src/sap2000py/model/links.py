"""Link (two-joint) elements: bearings, isolators, dampers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..handles import Handle
from ._base import Manager
from .groups import GroupHandle
from .link_props import LinkPropHandle
from .points import PointHandle


@dataclass(frozen=True, eq=False)
class LinkHandle(Handle):
    """A live link object reference."""

    _manager_path: ClassVar[str] = "m.links"

    def delete(self) -> None:
        """Delete this link object."""
        owner = self._require_owner()
        owner._g.call(owner._raw.LinkObj.Delete, self.name, api_name="LinkObj.Delete")

    def group(self, group: GroupHandle | str, *, remove: bool = False) -> LinkHandle:
        """Assign this link to a group. Wraps ``LinkObj.SetGroupAssign``."""
        owner = self._require_owner()
        group_ref = owner._model.groups.ref(group)
        owner._g.call(
            owner._raw.LinkObj.SetGroupAssign,
            self.name,
            group_ref.name,
            remove,
            api_name="LinkObj.SetGroupAssign",
        )
        return self


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
        point_i_ref = self._model.points._checked_ref(point_i)
        point_j_ref = self._model.points._checked_ref(point_j)
        prop_ref = self._model.link_props._checked_ref(prop)
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
