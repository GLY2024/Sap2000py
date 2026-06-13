"""Link properties — the force-deformation laws a link element references.

A bearing, isolator or damper is modelled as a *link element* that points at a
*link property*. This manager defines the property; :class:`~sap2000py.model.links.Links`
creates the element. Only the linear property is wrapped here — the everyday
bridge bearing — with the nonlinear laws reachable through ``client.api.PropLink``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..handles import LinkPropHandle
from ._base import Manager


def _bool6(values: Sequence[bool] | None, *, default: bool) -> list[bool]:
    if values is None:
        return [default] * 6
    if len(values) != 6:
        raise ValueError(f"expected 6 elements [U1..R3], got {len(values)}.")
    return [bool(v) for v in values]


class LinkProps(Manager):
    """Define link properties. Wraps ``cPropLink``."""

    def add_linear(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        damping: Sequence[float] | None = None,
        dof: Sequence[bool] | None = None,
        fixed: Sequence[bool] | None = None,
        notes: str = "",
    ) -> LinkPropHandle:
        """Define a linear link property. Wraps ``PropLink.SetLinear``.

        Parameters
        ----------
        stiffness:
            Effective stiffness ``Ke`` for ``[U1, U2, U3, R1, R2, R3]`` in the
            current units.
        damping:
            Effective damping ``Ce`` per DOF; defaults to zero.
        dof:
            Which DOF are active; defaults to all six.
        fixed:
            Which active DOF are rigid (their stiffness is ignored); defaults to
            none.
        """
        if len(stiffness) != 6:
            raise ValueError(f"stiffness must have 6 elements [U1..R3], got {len(stiffness)}.")
        ke = [float(k) for k in stiffness]
        ce = [0.0] * 6 if damping is None else [float(c) for c in damping]
        if len(ce) != 6:
            raise ValueError(f"damping must have 6 elements [U1..R3], got {len(ce)}.")
        # SetLinear(Name, DOF[6], Fixed[6], Ke[6], Ce[6], DJ2, DJ3,
        #           KeCoupled, CeCoupled, Notes, GUID)
        self._g.call(
            self._raw.PropLink.SetLinear,
            name,
            _bool6(dof, default=True),
            _bool6(fixed, default=False),
            ke,
            ce,
            0.0,
            0.0,
            False,
            False,
            notes,
            "",
            api_name="PropLink.SetLinear",
        )
        return LinkPropHandle(name, _owner=self)

    def names(self) -> list[str]:
        """All link property names. Wraps ``PropLink.GetNameList``."""
        _count, names = self._g.call(
            self._raw.PropLink.GetNameList, api_name="PropLink.GetNameList"
        )
        return list(names) if names else []

    def delete(self, prop: LinkPropHandle | str) -> None:
        """Delete a link property. Wraps ``PropLink.Delete``."""
        from ..handles import as_name

        self._g.call(self._raw.PropLink.Delete, as_name(prop), api_name="PropLink.Delete")
