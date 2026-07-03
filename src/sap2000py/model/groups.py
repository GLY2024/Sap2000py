"""Named groups of objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..handles import Handle
from ._base import Manager


@dataclass(frozen=True, eq=False)
class GroupHandle(Handle):
    """A live group definition reference."""

    _manager_path: ClassVar[str] = "m.groups"

    def delete(self) -> None:
        """Delete this group definition."""
        owner = self._require_owner()
        owner._g.call(owner._raw.GroupDef.Delete, self.name, api_name="GroupDef.Delete")


class Groups(Manager[GroupHandle]):
    """Define and query groups. Wraps ``cGroup``.

    Assigning objects to a group is done from live handles, e.g.
    ``model.frames.ref(frame).group(group)``.
    """

    _handle_cls = GroupHandle
    _kind = "group"

    def add(self, name: str) -> GroupHandle:
        """Create (or redefine) a group. Wraps ``GroupDef.SetGroup``."""
        self._g.call(self._raw.GroupDef.SetGroup, name, api_name="GroupDef.SetGroup")
        return self._handle(name)

    def names(self) -> list[str]:
        """All group names. Wraps ``GroupDef.GetNameList``."""
        _count, names = self._g.call(
            self._raw.GroupDef.GetNameList, api_name="GroupDef.GetNameList"
        )
        return list(names) if names else []
