"""Named groups of objects."""

from __future__ import annotations

from ..handles import GroupHandle, as_name
from ._base import Manager


class Groups(Manager):
    """Define and query groups. Wraps ``cGroup``.

    Assigning objects to a group is done from the object managers, e.g.
    ``model.frames.add_to_group(frame, group)``.
    """

    def add(self, name: str) -> GroupHandle:
        """Create (or redefine) a group. Wraps ``GroupDef.SetGroup``."""
        self._g.call(self._raw.GroupDef.SetGroup, name, api_name="GroupDef.SetGroup")
        return GroupHandle(name, _owner=self)

    def names(self) -> list[str]:
        """All group names. Wraps ``GroupDef.GetNameList``."""
        _count, names = self._g.call(
            self._raw.GroupDef.GetNameList, api_name="GroupDef.GetNameList"
        )
        return list(names) if names else []

    def delete(self, group: GroupHandle | str) -> None:
        """Delete a group (objects are not deleted). Wraps ``GroupDef.Delete``."""
        self._g.call(self._raw.GroupDef.Delete, as_name(group), api_name="GroupDef.Delete")
