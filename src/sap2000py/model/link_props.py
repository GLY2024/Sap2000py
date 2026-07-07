"""Link properties — the force-deformation laws a link element references.

A bearing, isolator or damper is modelled as a *link element* that points at a
*link property*. This manager defines the property; :class:`~sap2000py.model.links.Links`
creates the element. Only the linear property is wrapped here — the everyday
bridge bearing — with the nonlinear laws reachable through ``client.api.PropLink``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar, Literal

from ..enums import DOF_NAMES, DofSpec, to_dof_mask
from ..handles import Handle
from ._base import Manager

_DofName = Literal["U1", "U2", "U3", "R1", "R2", "R3"]
_DOF_INDEX = {name: index for index, name in enumerate(DOF_NAMES)}


@dataclass(frozen=True)
class WenDof:
    """Plastic-Wen nonlinear parameters for one DOF."""

    k: float
    yield_force: float
    post_yield_ratio: float
    exponent: float = 2.0


@dataclass(frozen=True)
class FrictionDof:
    """Friction-isolator nonlinear parameters for one DOF."""

    k: float
    friction_slow: float
    friction_fast: float
    rate: float
    radius: float = 0.0


@dataclass(frozen=True)
class GapHookDof:
    """Gap or hook nonlinear parameters for one DOF."""

    k: float
    opening: float


@dataclass(frozen=True)
class DamperDof:
    """Exponential damper nonlinear parameters for one DOF."""

    k: float
    c: float
    exponent: float = 1.0


def _six(name: str, values: Sequence[float]) -> list[float]:
    if len(values) != 6:
        raise ValueError(f"{name} must have 6 elements [U1..R3], got {len(values)}.")
    return [float(value) for value in values]


def _zeros() -> list[float]:
    return [0.0] * 6


def _nonlinear_mask(keys: Mapping[_DofName, object]) -> list[bool]:
    mask = [False] * 6
    for dof in keys:
        mask[_DOF_INDEX[dof]] = True
    return mask


@dataclass(frozen=True, eq=False)
class LinkPropHandle(Handle):
    """A live link property reference."""

    _manager_path: ClassVar[str] = "m.link_props"

    def delete(self) -> None:
        """Delete this link property."""
        owner = self._require_owner()
        owner._g.call(owner._raw.PropLink.Delete, self.name, api_name="PropLink.Delete")


class LinkProps(Manager[LinkPropHandle]):
    """Define link properties. Wraps ``cPropLink``."""

    _handle_cls = LinkPropHandle
    _kind = "link property"

    def add_linear(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
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
        ke = _six("stiffness", stiffness)
        ce = _zeros() if damping is None else _six("damping", damping)
        # SetLinear(Name, DOF[6], Fixed[6], Ke[6], Ce[6], DJ2, DJ3,
        #           KeCoupled, CeCoupled, Notes, GUID)
        self._g.call(
            self._raw.PropLink.SetLinear,
            name,
            to_dof_mask(dof, default=True),
            to_dof_mask(fixed, default=False),
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

    def add_plastic_wen(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        nonlinear: Mapping[_DofName, WenDof],
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
        dj2: float = 0.0,
        dj3: float = 0.0,
        notes: str = "",
    ) -> LinkPropHandle:
        """Define a plastic-Wen link property.

        Wraps ``PropLink.SetPlasticWen``.
        """
        k = _zeros()
        yield_force = _zeros()
        ratio = _zeros()
        exponent = _zeros()
        for dof_name, params in nonlinear.items():
            index = _DOF_INDEX[dof_name]
            k[index] = float(params.k)
            yield_force[index] = float(params.yield_force)
            ratio[index] = float(params.post_yield_ratio)
            exponent[index] = float(params.exponent)
        self._g.call(
            self._raw.PropLink.SetPlasticWen,
            name,
            to_dof_mask(dof, default=True),
            to_dof_mask(fixed, default=False),
            _nonlinear_mask(nonlinear),
            _six("stiffness", stiffness),
            _zeros() if damping is None else _six("damping", damping),
            k,
            yield_force,
            ratio,
            exponent,
            float(dj2),
            float(dj3),
            notes,
            api_name="PropLink.SetPlasticWen",
        )
        return self._handle(name)

    def add_friction_isolator(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        nonlinear: Mapping[_DofName, FrictionDof],
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
        axial_damping: float = 0.0,
        dj2: float = 0.0,
        dj3: float = 0.0,
    ) -> LinkPropHandle:
        """Define a friction-isolator link property.

        Wraps ``PropLink.SetFrictionIsolator``.
        """
        k = _zeros()
        slow = _zeros()
        fast = _zeros()
        rate = _zeros()
        radius = _zeros()
        for dof_name, params in nonlinear.items():
            index = _DOF_INDEX[dof_name]
            k[index] = float(params.k)
            slow[index] = float(params.friction_slow)
            fast[index] = float(params.friction_fast)
            rate[index] = float(params.rate)
            radius[index] = float(params.radius)
        self._g.call(
            self._raw.PropLink.SetFrictionIsolator,
            name,
            to_dof_mask(dof, default=True),
            to_dof_mask(fixed, default=False),
            _nonlinear_mask(nonlinear),
            _six("stiffness", stiffness),
            _zeros() if damping is None else _six("damping", damping),
            k,
            slow,
            fast,
            rate,
            radius,
            float(axial_damping),
            float(dj2),
            float(dj3),
            api_name="PropLink.SetFrictionIsolator",
        )
        return self._handle(name)

    def add_gap(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        nonlinear: Mapping[_DofName, GapHookDof],
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
        dj2: float = 0.0,
        dj3: float = 0.0,
    ) -> LinkPropHandle:
        """Define a gap link property.

        Wraps ``PropLink.SetGap``.
        """
        self._add_gap_or_hook(
            name,
            "SetGap",
            stiffness,
            nonlinear=nonlinear,
            damping=damping,
            dof=dof,
            fixed=fixed,
            dj2=dj2,
            dj3=dj3,
        )
        return self._handle(name)

    def add_hook(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        nonlinear: Mapping[_DofName, GapHookDof],
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
        dj2: float = 0.0,
        dj3: float = 0.0,
    ) -> LinkPropHandle:
        """Define a hook link property.

        Wraps ``PropLink.SetHook``.
        """
        self._add_gap_or_hook(
            name,
            "SetHook",
            stiffness,
            nonlinear=nonlinear,
            damping=damping,
            dof=dof,
            fixed=fixed,
            dj2=dj2,
            dj3=dj3,
        )
        return self._handle(name)

    def add_damper(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        nonlinear: Mapping[_DofName, DamperDof],
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
        dj2: float = 0.0,
        dj3: float = 0.0,
    ) -> LinkPropHandle:
        """Define an exponential damper link property.

        Wraps ``PropLink.SetDamper``.
        """
        k = _zeros()
        c = _zeros()
        exponent = _zeros()
        for dof_name, params in nonlinear.items():
            index = _DOF_INDEX[dof_name]
            k[index] = float(params.k)
            c[index] = float(params.c)
            exponent[index] = float(params.exponent)
        self._g.call(
            self._raw.PropLink.SetDamper,
            name,
            to_dof_mask(dof, default=True),
            to_dof_mask(fixed, default=False),
            _nonlinear_mask(nonlinear),
            _six("stiffness", stiffness),
            _zeros() if damping is None else _six("damping", damping),
            k,
            c,
            exponent,
            float(dj2),
            float(dj3),
            api_name="PropLink.SetDamper",
        )
        return self._handle(name)

    def add_multilinear_elastic(
        self,
        name: str,
        stiffness: Sequence[float],
        *,
        curves: Mapping[_DofName, Sequence[tuple[float, float]]],
        damping: Sequence[float] | None = None,
        dof: DofSpec = None,
        fixed: DofSpec = None,
        dj2: float = 0.0,
        dj3: float = 0.0,
        notes: str = "",
    ) -> LinkPropHandle:
        """Define a multilinear elastic link property.

        Wraps ``PropLink.SetMultiLinearElastic``.
        """
        self._g.call(
            self._raw.PropLink.SetMultiLinearElastic,
            name,
            to_dof_mask(dof, default=True),
            to_dof_mask(fixed, default=False),
            _nonlinear_mask(curves),
            _six("stiffness", stiffness),
            _zeros() if damping is None else _six("damping", damping),
            float(dj2),
            float(dj3),
            notes,
            "",
            api_name="PropLink.SetMultiLinearElastic",
        )
        for dof_name, curve in curves.items():
            force = [float(point[0]) for point in curve]
            deformation = [float(point[1]) for point in curve]
            self._g.call(
                self._raw.PropLink.SetMultiLinearPoints,
                name,
                _DOF_INDEX[dof_name] + 1,
                len(curve),
                force,
                deformation,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                api_name="PropLink.SetMultiLinearPoints",
            )
        return self._handle(name)

    def _add_gap_or_hook(
        self,
        name: str,
        method_name: Literal["SetGap", "SetHook"],
        stiffness: Sequence[float],
        *,
        nonlinear: Mapping[_DofName, GapHookDof],
        damping: Sequence[float] | None,
        dof: DofSpec,
        fixed: DofSpec,
        dj2: float,
        dj3: float,
    ) -> None:
        k = _zeros()
        opening = _zeros()
        for dof_name, params in nonlinear.items():
            index = _DOF_INDEX[dof_name]
            k[index] = float(params.k)
            opening[index] = float(params.opening)
        com_func = (
            self._raw.PropLink.SetGap
            if method_name == "SetGap"
            else self._raw.PropLink.SetHook
        )
        self._g.call(
            com_func,
            name,
            to_dof_mask(dof, default=True),
            to_dof_mask(fixed, default=False),
            _nonlinear_mask(nonlinear),
            _six("stiffness", stiffness),
            _zeros() if damping is None else _six("damping", damping),
            k,
            opening,
            float(dj2),
            float(dj3),
            api_name=f"PropLink.{method_name}",
        )

    def names(self) -> list[str]:
        """All link property names. Wraps ``PropLink.GetNameList``."""
        _count, names = self._g.call(
            self._raw.PropLink.GetNameList, api_name="PropLink.GetNameList"
        )
        return list(names) if names else []
