"""Joint constraints (Body / Equal) that tie degrees of freedom together.

A *constraint* is a named definition (e.g. a rigid Body link); points are then
assigned to it with :meth:`~sap2000py.model.points.PointHandle.constrain`. This
is how the bridge layer's ``snap_connect`` rigidly joins coincident nodes (cap
to pier, pier-top to bearing-bottom) without modelling stiff link elements.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..enums import to_dof_mask
from ._base import Manager

DofSpec = str | Sequence[str] | Sequence[bool] | None


class Constraints(Manager):
    """Define joint constraints. Wraps ``cConstraintDef``."""

    def add_body(
        self,
        name: str,
        *,
        dof: DofSpec = None,
        csys: str = "Global",
    ) -> str:
        """Define a Body constraint (rigid body). Wraps ``ConstraintDef.SetBody``.

        ``dof`` selects which of ``[U1, U2, U3, R1, R2, R3]`` are tied; the
        default rigidly couples all six. Returns the constraint name.
        """
        # SetBody(Name, Value[6], CSys)
        self._g.call(
            self._raw.ConstraintDef.SetBody,
            name,
            to_dof_mask(dof, default=True),
            csys,
            api_name="ConstraintDef.SetBody",
        )
        return name

    def add_equal(
        self,
        name: str,
        *,
        dof: DofSpec = None,
        csys: str = "Global",
    ) -> str:
        """Define an Equal constraint. Wraps ``ConstraintDef.SetEqual``.

        Equal constraints make the selected DOF equal across the assigned joints
        (they translate/rotate together) without enforcing full rigid-body
        kinematics. Returns the constraint name.
        """
        # SetEqual(Name, Value[6], CSys)
        self._g.call(
            self._raw.ConstraintDef.SetEqual,
            name,
            to_dof_mask(dof, default=True),
            csys,
            api_name="ConstraintDef.SetEqual",
        )
        return name

    def names(self) -> list[str]:
        """All constraint names. Wraps ``ConstraintDef.GetNameList``."""
        _count, names = self._g.call(
            self._raw.ConstraintDef.GetNameList, api_name="ConstraintDef.GetNameList"
        )
        return list(names) if names else []

    def delete(self, name: str) -> None:
        """Delete a constraint definition. Wraps ``ConstraintDef.Delete``."""
        self._g.call(self._raw.ConstraintDef.Delete, name, api_name="ConstraintDef.Delete")
