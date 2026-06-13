"""Auto-connection between component anchors.

``snap_connect`` ties two (usually coincident) joints together with one of three
strategies, so assembling a bridge never means hand-writing constraint or link
boilerplate at every cap/pier/bearing interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING

from ..enums import DOF
from ..handles import PointHandle, as_name

if TYPE_CHECKING:
    from ..model import Model

#: Stiffness used for every DOF of a rigid link property. The DOF are also marked
#: ``fixed`` (so SAP ignores the value), but a large number keeps the property
#: well-defined if a caller un-fixes a DOF.
_RIGID_STIFFNESS = 1.0e12


class Connection(str, Enum):
    """How :func:`snap_connect` joins two joints."""

    BODY = "body"
    """Rigid-body joint constraint: the joints move as one rigid body."""
    EQUAL = "equal"
    """Equal-DOF constraint: the selected DOF are made equal across the joints."""
    RIGID_LINK = "rigid_link"
    """A stiff two-joint link element (use when a constraint is unsuitable)."""


def snap_connect(
    model: Model,
    a: PointHandle | str,
    b: PointHandle | str,
    *,
    how: Connection | str = Connection.BODY,
    dof: Sequence[bool] | None = None,
    name: str = "",
) -> str:
    """Connect joints ``a`` and ``b``; return the constraint or link name.

    Parameters
    ----------
    how:
        :class:`Connection` strategy. ``BODY`` and ``EQUAL`` create joint
        constraints; ``RIGID_LINK`` creates a stiff link element.
    dof:
        Six-element ``[U1..R3]`` mask of which DOF to couple; defaults to all
        six. Ignored by ``RIGID_LINK`` (all DOF are rigid).

    Notes
    -----
    To truly *merge* two coincident nodes into one, create the second point with
    ``model.points.add(..., merge=True)`` instead — merging happens at point
    creation, not after the fact.
    """
    how = Connection(how)
    dof6 = DOF.fixed() if dof is None else list(dof)
    label = name or f"{as_name(a)}~{as_name(b)}"

    if how is Connection.RIGID_LINK:
        prop = f"{label}_rigid"
        model.link_props.add_linear(prop, [_RIGID_STIFFNESS] * 6, fixed=[True] * 6)
        link = model.links.add_by_points(a, b, prop, name=label)
        return link.name

    if how is Connection.BODY:
        model.constraints.add_body(label, dof=dof6)
    else:  # EQUAL
        model.constraints.add_equal(label, dof=dof6)
    model.points.set_constraint(a, label)
    model.points.set_constraint(b, label)
    return label
