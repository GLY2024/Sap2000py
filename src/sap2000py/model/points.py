"""Point (joint) objects: create, query, restrain."""

from __future__ import annotations

from collections.abc import Sequence

from ..enums import ItemType
from ..handles import PointHandle, as_name
from ._base import Manager


class Points(Manager):
    """Create and manipulate point objects. Wraps ``cPointObj``."""

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

        Parameters
        ----------
        name:
            Desired name; if empty or already taken, SAP2000 assigns one.
        merge:
            When ``True`` (default), a point added at an existing point's
            location is merged into it.

        Returns the handle of the point that now exists at that location (which,
        when merged, is the pre-existing point). Wraps ``PointObj.AddCartesian``.
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

    def coordinates(
        self, point: PointHandle | str, *, csys: str = "Global"
    ) -> tuple[float, float, float]:
        """Return ``(x, y, z)`` of a point. Wraps ``PointObj.GetCoordCartesian``."""
        # GetCoordCartesian(Name, X[in,out], Y, Z, CSys) -> (X, Y, Z)
        x, y, z = self._g.call(
            self._raw.PointObj.GetCoordCartesian,
            as_name(point),
            0.0,
            0.0,
            0.0,
            csys,
            api_name="PointObj.GetCoordCartesian",
        )
        return float(x), float(y), float(z)

    def set_restraints(
        self,
        point: PointHandle | str,
        dof: Sequence[bool],
        *,
        item_type: ItemType = ItemType.OBJECT,
    ) -> None:
        """Set the six restraint DOF ``[U1, U2, U3, R1, R2, R3]``.

        Build the mask with :class:`~sap2000py.enums.DOF`, e.g.
        ``set_restraints(p, DOF.fixed())``. Wraps ``PointObj.SetRestraint``.
        """
        if len(dof) != 6:
            raise ValueError(f"dof must have 6 elements [U1..R3], got {len(dof)}.")
        self._g.call(
            self._raw.PointObj.SetRestraint,
            as_name(point),
            list(dof),
            int(item_type),
            api_name="PointObj.SetRestraint",
        )

    def delete(self, point: PointHandle | str, *, item_type: ItemType = ItemType.OBJECT) -> None:
        """Delete a point object. Wraps ``PointObj.Delete``."""
        self._g.call(
            self._raw.PointObj.Delete,
            as_name(point),
            int(item_type),
            api_name="PointObj.Delete",
        )
