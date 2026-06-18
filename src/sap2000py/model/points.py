"""Point (joint) objects: create, query, restrain."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

from ..enums import ItemType, to_dof_mask
from ..handles import Handle
from ._base import Manager

DofSpec = str | Sequence[str] | Sequence[bool] | None


@dataclass(frozen=True)
class PointHandle(Handle):
    """A live point (joint) object reference."""

    _manager_path: ClassVar[str] = "m.points"

    def restrain(self, dof: DofSpec) -> PointHandle:
        """Set point restraints and return ``self`` for chaining."""
        owner = self._require_owner()
        owner._g.call(
            owner._raw.PointObj.SetRestraint,
            self.name,
            to_dof_mask(dof),
            int(ItemType.OBJECT),
            api_name="PointObj.SetRestraint",
        )
        return self

    def spring(
        self,
        stiffness: Sequence[float],
        *,
        local_csys: bool = False,
        replace: bool = True,
    ) -> PointHandle:
        """Assign six uncoupled spring stiffnesses and return ``self``."""
        if len(stiffness) != 6:
            raise ValueError(f"stiffness must have 6 elements [U1..R3], got {len(stiffness)}.")
        owner = self._require_owner()
        owner._g.call(
            owner._raw.PointObj.SetSpring,
            self.name,
            [float(k) for k in stiffness],
            int(ItemType.OBJECT),
            local_csys,
            replace,
            api_name="PointObj.SetSpring",
        )
        return self

    def constrain(self, name: str, *, replace: bool = False) -> PointHandle:
        """Assign this point to a named joint constraint and return ``self``."""
        owner = self._require_owner()
        owner._g.call(
            owner._raw.PointObj.SetConstraint,
            self.name,
            name,
            int(ItemType.OBJECT),
            replace,
            api_name="PointObj.SetConstraint",
        )
        return self

    def coordinates(self, *, csys: str = "Global") -> tuple[float, float, float]:
        """Return ``(x, y, z)`` in ``csys``."""
        owner = self._require_owner()
        x, y, z = owner._g.call(
            owner._raw.PointObj.GetCoordCartesian,
            self.name,
            0.0,
            0.0,
            0.0,
            csys,
            api_name="PointObj.GetCoordCartesian",
        )
        return float(x), float(y), float(z)

    def reactions(self) -> Any:
        """Joint reactions for the currently selected output cases/combos."""
        owner = self._require_owner()
        return owner._model.results.joint_reactions(self)

    def displacements(self) -> Any:
        """Joint displacements for the currently selected output cases/combos."""
        owner = self._require_owner()
        return owner._model.results.joint_displacements(self)

    def delete(self) -> None:
        """Delete this point object."""
        owner = self._require_owner()
        owner._g.call(
            owner._raw.PointObj.Delete,
            self.name,
            int(ItemType.OBJECT),
            api_name="PointObj.Delete",
        )


class Points(Manager):
    """Create and manipulate point objects. Wraps ``cPointObj``."""

    _handle_cls = PointHandle
    _kind = "point"

    def _handle(self, name: str) -> PointHandle:
        return PointHandle(name, _owner=self)

    def add(
        self,
        x: float,
        y: float,
        z: float,
        *,
        name: str = "",
        csys: str = "Global",
        merge: bool = True,
    ) -> PointHandle:
        """Add a point at Cartesian ``(x, y, z)`` in the current length unit.

        Wraps ``PointObj.AddCartesian``.

        Parameters
        ----------
        name:
            Desired name; if empty or already taken, SAP2000 assigns one.
        merge:
            When ``True`` (default), a point added at an existing point's
            location is merged into it.

        Returns
        -------
        PointHandle
            The point that now exists at that location — the pre-existing point
            when merged.
        """
        # AddCartesian(X, Y, Z, Name[in,out], UserName, CSys, MergeOff, MergeNumber)
        assigned = self._g.call(
            self._raw.PointObj.AddCartesian,
            float(x),
            float(y),
            float(z),
            "",
            name,
            csys,
            not merge,
            0,
            api_name="PointObj.AddCartesian",
        )
        return self._handle(assigned)

    def count(self) -> int:
        """Number of point objects in the model. Wraps ``PointObj.Count``."""
        return int(self._g.value(self._raw.PointObj.Count, api_name="PointObj.Count"))

    def names(self) -> list[str]:
        """All point object names. Wraps ``PointObj.GetNameList``."""
        result = self._g.call(self._raw.PointObj.GetNameList, api_name="PointObj.GetNameList")
        _count, names = result
        return list(names) if names else []
