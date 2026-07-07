"""Engineering demand parameter extractors."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from ..handles import Handle

if TYPE_CHECKING:
    from ..bridge.systems import BridgeBuild
    from ..model import Model
    from ..model.results import ResultTable

_TransDof = Literal["U1", "U2"]
_HingeQuantity = Literal["plastic_rotation", "curvature_ductility"]


class Edp(Protocol):
    """Protocol for one-case peak absolute demand extraction."""

    @property
    def name(self) -> str:
        """EDP name."""
        ...

    def extract(self, model: Model, case: str) -> float:
        """Return the peak absolute demand for ``case``."""


@dataclass(frozen=True)
class PierDrift:
    """Peak relative displacement divided by pier height.

    Parameters
    ----------
    name:
        EDP name.
    top:
        Top joint name or handle.
    bottom:
        Bottom joint name or handle.
    height:
        Pier height.
    dof:
        Translational displacement component to use.
    """

    name: str
    top: Handle | str
    bottom: Handle | str
    height: float
    dof: _TransDof = "U1"

    def __post_init__(self) -> None:
        if self.height <= 0.0:
            raise ValueError("height must be positive.")

    def extract(self, model: Model, case: str) -> float:
        top = _series(model.results.joint_displacements(_handle_name(self.top)), case, self.dof)
        bottom = _series(
            model.results.joint_displacements(_handle_name(self.bottom)),
            case,
            self.dof,
        )
        steps = sorted(set(top) & set(bottom), key=_step_sort_key)
        if not steps:
            raise ValueError(
                f"no common displacement steps for EDP {self.name!r} in case {case!r}."
            )
        demand = max(abs(top[step] - bottom[step]) for step in steps)
        return float(demand / self.height)


@dataclass(frozen=True)
class BearingDeformation:
    """Peak absolute link deformation."""

    name: str
    link: Handle | str
    dof: _TransDof = "U1"

    def extract(self, model: Model, case: str) -> float:
        table = model.results.link_deformations(_handle_name(self.link))
        values = [abs(value) for _step, value in _series(table, case, self.dof).items()]
        if not values:
            raise ValueError(f"no link deformation rows for EDP {self.name!r} in case {case!r}.")
        return float(max(values))


@dataclass(frozen=True)
class HingeStateEdp:
    """Best-effort hinge state demand read from SAP2000 database tables."""

    name: str
    hinge: str
    quantity: _HingeQuantity

    def extract(self, model: Model, case: str) -> float:
        table = model.hinges.states()
        hinge_col = _find_column(table.names, ("hinge", "hinge name", "hinge label"))
        case_col = _find_column(table.names, ("case", "outputcase", "output case"), required=False)
        value_col = _find_column(table.names, _quantity_candidates(self.quantity))
        if hinge_col is None or value_col is None:
            raise ValueError(f"missing hinge state columns for EDP {self.name!r}.")
        values: list[float] = []
        for row in table.rows():
            if str(row[hinge_col]) != self.hinge:
                continue
            if case_col is not None and str(row[case_col]) != case:
                continue
            values.append(abs(float(row[value_col])))
        if not values:
            raise ValueError(f"no hinge state rows for EDP {self.name!r} in case {case!r}.")
        return float(max(values))


def bridge_edps(
    build: BridgeBuild,
    *,
    piers: bool = True,
    bearings: bool = True,
    dof: _TransDof = "U1",
) -> list[Edp]:
    """Create pier-drift and bearing-deformation EDPs from a bridge build."""
    edps: list[Edp] = []
    if piers:
        for pier in build.piers:
            edps.append(
                PierDrift(
                    name=f"{pier.name}_drift_{dof}",
                    top=pier.anchor("top"),
                    bottom=pier.anchor("bottom"),
                    height=pier.height,
                    dof=dof,
                )
            )
    if bearings:
        for bearing in build.bearings:
            edps.append(
                BearingDeformation(
                    name=f"{bearing.name}_deformation_{dof}",
                    link=bearing.name,
                    dof=dof,
                )
            )
    return edps


def _series(table: ResultTable, case: str, dof: str) -> dict[object, float]:
    if dof not in table.names:
        raise ValueError(f"result table has no {dof!r} column.")
    series: dict[object, float] = {}
    for row in table.rows():
        if str(row["case"]) == case:
            series[row["step"]] = float(row[dof])
    return series


def _handle_name(obj: Handle | str) -> str:
    return obj.name if isinstance(obj, Handle) else obj


def _step_sort_key(step: object) -> tuple[int, object]:
    if isinstance(step, int | float):
        return (0, float(step))
    return (1, str(step))


def _find_column(
    names: Iterable[str],
    candidates: Iterable[str],
    *,
    required: bool = True,
) -> str | None:
    lookup = {_normalize(name): name for name in names}
    for candidate in candidates:
        key = _normalize(candidate)
        if key in lookup:
            return lookup[key]
    if not required:
        return None
    raise ValueError(f"none of the result columns {tuple(candidates)!r} were found.")


def _normalize(value: str) -> str:
    return value.lower().replace(" ", "").replace("_", "")


def _quantity_candidates(quantity: _HingeQuantity) -> tuple[str, ...]:
    if quantity == "plastic_rotation":
        return ("plastic_rotation", "plastic rotation", "plastic rot", "rotation")
    return ("curvature_ductility", "curvature ductility", "ductility")
