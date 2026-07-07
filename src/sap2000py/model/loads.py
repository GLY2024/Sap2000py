"""Load patterns, load cases, and combinations.

This collapses the old ``Sapload.py`` (13 near-identical ``load_*`` classes,
~1,300 lines) into two small managers with parameterized methods.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ..enums import (
    DirectionalCombo,
    GeomNonlinearity,
    LoadPatternType,
    ModalCombo,
    ProportionalDampingType,
    TimeIntegrationMethod,
)
from ..handles import Handle
from ._base import Manager
from .functions import FunctionHandle
from .points import PointHandle

_DofName = Literal["U1", "U2", "U3", "R1", "R2", "R3"]
_LoadKind = Literal["accel", "load"]
_StaticResultsSaved = Literal["final", "multiple"]

_DOF_INDEX = {"U1": 1, "U2": 2, "U3": 3, "R1": 4, "R2": 5, "R3": 6}


@dataclass(frozen=True)
class SpectrumLoad:
    """One response-spectrum load row."""

    direction: _DofName
    function: FunctionHandle | str
    scale: float = 1.0
    csys: str = "Global"
    angle: float = 0.0


@dataclass(frozen=True)
class HistoryLoad:
    """One time-history load row."""

    function: FunctionHandle | str
    load: str = "U1"
    kind: _LoadKind = "accel"
    scale: float = 1.0
    time_factor: float = 1.0
    arrival: float = 0.0
    csys: str = "Global"
    angle: float = 0.0


@dataclass(frozen=True)
class RayleighDamping:
    """Proportional damping payload for direct-history cases."""

    kind: ProportionalDampingType
    a: float = 0.0
    b: float = 0.0
    f1: float = 0.0
    f2: float = 0.0
    d1: float = 0.0
    d2: float = 0.0

    @classmethod
    def from_coefficients(cls, mass: float, stiffness: float) -> RayleighDamping:
        """Create mass/stiffness proportional damping from coefficients."""
        return cls(ProportionalDampingType.MASS_STIFFNESS, a=float(mass), b=float(stiffness))

    @classmethod
    def from_periods(cls, t1: float, t2: float, damping: float) -> RayleighDamping:
        """Create proportional damping from two periods and one damping ratio."""
        return cls(
            ProportionalDampingType.PERIOD,
            f1=float(t1),
            f2=float(t2),
            d1=float(damping),
            d2=float(damping),
        )

    @classmethod
    def from_frequencies(cls, f1: float, f2: float, damping: float) -> RayleighDamping:
        """Create proportional damping from two frequencies and one damping ratio."""
        return cls(
            ProportionalDampingType.FREQUENCY,
            f1=float(f1),
            f2=float(f2),
            d1=float(damping),
            d2=float(damping),
        )


@dataclass(frozen=True)
class TimeIntegration:
    """Direct-history time integration payload."""

    method: TimeIntegrationMethod = TimeIntegrationMethod.HHT
    alpha: float = 0.0
    beta: float = 0.25
    gamma: float = 0.5
    theta: float = 1.0

    @classmethod
    def newmark(cls, gamma: float = 0.5, beta: float = 0.25) -> TimeIntegration:
        """Create Newmark integration parameters."""
        return cls(TimeIntegrationMethod.NEWMARK, beta=float(beta), gamma=float(gamma))

    @classmethod
    def wilson(cls, theta: float = 1.4) -> TimeIntegration:
        """Create Wilson integration parameters."""
        return cls(TimeIntegrationMethod.WILSON, theta=float(theta))

    @classmethod
    def hht(cls, alpha: float = 0.0) -> TimeIntegration:
        """Create Hilber-Hughes-Taylor integration parameters."""
        return cls(TimeIntegrationMethod.HHT, alpha=float(alpha))


def _function_name(function: FunctionHandle | str) -> str:
    return function.name if isinstance(function, FunctionHandle) else function


class LoadPatterns(Manager[Handle]):
    """Define load patterns. Wraps ``cLoadPatterns``. Reached as ``model.loads.patterns``."""

    def add(
        self,
        name: str,
        *,
        pattern_type: LoadPatternType = LoadPatternType.DEAD,
        self_weight: float = 0.0,
        add_case: bool = True,
    ) -> str:
        """Add a load pattern (optionally with a matching static linear case).

        ``self_weight`` is the self-weight multiplier. Wraps ``LoadPatterns.Add``.

        Note that a blank model already contains a default ``"DEAD"`` pattern
        (self-weight multiplier 1.0); adding another with the same name fails.
        Use :meth:`set_self_weight` to adjust an existing pattern.
        """
        self._g.call(
            self._raw.LoadPatterns.Add,
            name,
            int(pattern_type),
            float(self_weight),
            add_case,
            api_name="LoadPatterns.Add",
        )
        return name

    def set_self_weight(self, name: str, multiplier: float) -> None:
        """Set an existing pattern's self-weight multiplier.

        Wraps ``LoadPatterns.SetSelfWTMultiplier``.
        """
        self._g.call(
            self._raw.LoadPatterns.SetSelfWTMultiplier,
            name,
            float(multiplier),
            api_name="LoadPatterns.SetSelfWTMultiplier",
        )

    def names(self) -> list[str]:
        """All load pattern names. Wraps ``LoadPatterns.GetNameList``."""
        _count, names = self._g.call(
            self._raw.LoadPatterns.GetNameList, api_name="LoadPatterns.GetNameList"
        )
        return list(names) if names else []


class LoadCases(Manager[Handle]):
    """Define load cases. Wraps ``cLoadCases``. Reached as ``model.loads.cases``."""

    def add_static_linear(self, name: str, *, loads: Mapping[str, float] | None = None) -> str:
        """Create a linear static case applying load patterns with scale factors.

        ``loads`` maps load-pattern name to scale factor. Wraps
        ``LoadCases.StaticLinear.SetCase`` + ``SetLoads``.
        """
        self._g.call(
            self._raw.LoadCases.StaticLinear.SetCase,
            name,
            api_name="LoadCases.StaticLinear.SetCase",
        )
        if loads:
            pattern_names = list(loads)
            self._g.call(
                self._raw.LoadCases.StaticLinear.SetLoads,
                name,
                len(pattern_names),
                ["Load"] * len(pattern_names),
                pattern_names,
                [float(loads[p]) for p in pattern_names],
                api_name="LoadCases.StaticLinear.SetLoads",
            )
        return name

    def add_modal_eigen(self, name: str, *, num_modes: int = 12, min_modes: int = 1) -> str:
        """Create an eigen modal case requesting ``num_modes`` modes.

        Wraps ``LoadCases.ModalEigen.SetCase`` + ``SetNumberModes``.
        """
        self._g.call(
            self._raw.LoadCases.ModalEigen.SetCase, name, api_name="LoadCases.ModalEigen.SetCase"
        )
        self._g.call(
            self._raw.LoadCases.ModalEigen.SetNumberModes,
            name,
            int(num_modes),
            int(min_modes),
            api_name="LoadCases.ModalEigen.SetNumberModes",
        )
        return name

    def add_modal_ritz(
        self,
        name: str,
        *,
        num_modes: int = 12,
        loads: Sequence[tuple[str, str]] | None = None,
    ) -> str:
        """Create a Ritz modal case requesting ``num_modes`` modes.

        Wraps ``LoadCases.ModalRitz.SetCase`` + ``SetNumberModes``.
        """
        self._g.call(
            self._raw.LoadCases.ModalRitz.SetCase, name, api_name="LoadCases.ModalRitz.SetCase"
        )
        self._g.call(
            self._raw.LoadCases.ModalRitz.SetNumberModes,
            name,
            int(num_modes),
            int(num_modes),
            api_name="LoadCases.ModalRitz.SetNumberModes",
        )
        if loads:
            load_types = [load_type for load_type, _load_name in loads]
            load_names = [load_name for _load_type, load_name in loads]
            self._g.call(
                self._raw.LoadCases.ModalRitz.SetLoads,
                name,
                len(loads),
                load_types,
                load_names,
                [0] * len(loads),
                [99] * len(loads),
                api_name="LoadCases.ModalRitz.SetLoads",
            )
        return name

    def add_response_spectrum(
        self,
        name: str,
        *,
        loads: Sequence[SpectrumLoad],
        modal_case: str = "MODAL",
        damping: float = 0.05,
        modal_combo: ModalCombo = ModalCombo.CQC,
        directional_combo: DirectionalCombo = DirectionalCombo.SRSS,
    ) -> str:
        """Create a response-spectrum case.

        Wraps ``LoadCases.ResponseSpectrum.SetCase``.
        """
        self._g.call(
            self._raw.LoadCases.ResponseSpectrum.SetCase,
            name,
            api_name="LoadCases.ResponseSpectrum.SetCase",
        )
        self._g.call(
            self._raw.LoadCases.ResponseSpectrum.SetModalCase,
            name,
            modal_case,
            api_name="LoadCases.ResponseSpectrum.SetModalCase",
        )
        self._g.call(
            self._raw.LoadCases.ResponseSpectrum.SetDampConstant,
            name,
            float(damping),
            api_name="LoadCases.ResponseSpectrum.SetDampConstant",
        )
        self._g.call(
            self._raw.LoadCases.ResponseSpectrum.SetModalComb_1,
            name,
            int(modal_combo),
            1.0,
            0.0,
            1,
            60.0,
            api_name="LoadCases.ResponseSpectrum.SetModalComb_1",
        )
        self._g.call(
            self._raw.LoadCases.ResponseSpectrum.SetDirComb,
            name,
            int(directional_combo),
            0.0,
            api_name="LoadCases.ResponseSpectrum.SetDirComb",
        )
        self._g.call(
            self._raw.LoadCases.ResponseSpectrum.SetLoads,
            name,
            len(loads),
            [load.direction for load in loads],
            [_function_name(load.function) for load in loads],
            [float(load.scale) for load in loads],
            [load.csys for load in loads],
            [float(load.angle) for load in loads],
            api_name="LoadCases.ResponseSpectrum.SetLoads",
        )
        return name

    def add_modal_history(
        self,
        name: str,
        *,
        loads: Sequence[HistoryLoad],
        steps: int,
        dt: float,
        modal_case: str = "MODAL",
        nonlinear: bool = True,
        damping: float = 0.05,
        initial_case: str | None = None,
    ) -> str:
        """Create a modal time-history case.

        Wraps ``LoadCases.ModHistNonLinear.SetCase`` or ``ModHistLinear.SetCase``.
        """
        case = (
            self._raw.LoadCases.ModHistNonLinear
            if nonlinear
            else self._raw.LoadCases.ModHistLinear
        )
        api_root = "LoadCases.ModHistNonLinear" if nonlinear else "LoadCases.ModHistLinear"
        self._g.call(case.SetCase, name, api_name=f"{api_root}.SetCase")
        self._g.call(case.SetModalCase, name, modal_case, api_name=f"{api_root}.SetModalCase")
        self._g.call(
            case.SetDampConstant,
            name,
            float(damping),
            api_name=f"{api_root}.SetDampConstant",
        )
        self._g.call(
            case.SetTimeStep,
            name,
            int(steps),
            float(dt),
            api_name=f"{api_root}.SetTimeStep",
        )
        if nonlinear and initial_case is not None:
            self._g.call(
                case.SetInitialCase,
                name,
                initial_case,
                api_name=f"{api_root}.SetInitialCase",
            )
        self._set_history_loads(case, api_root, name, loads)
        return name

    def add_direct_history(
        self,
        name: str,
        *,
        loads: Sequence[HistoryLoad],
        steps: int,
        dt: float,
        damping: RayleighDamping,
        nonlinear: bool = True,
        integration: TimeIntegration | None = None,
        initial_case: str | None = None,
        geometric_nonlinearity: GeomNonlinearity = GeomNonlinearity.NONE,
    ) -> str:
        """Create a direct-integration time-history case.

        Wraps ``LoadCases.DirHistNonLinear.SetCase`` or ``DirHistLinear.SetCase``.
        """
        integ = integration or TimeIntegration.hht()
        case = (
            self._raw.LoadCases.DirHistNonLinear
            if nonlinear
            else self._raw.LoadCases.DirHistLinear
        )
        api_root = "LoadCases.DirHistNonLinear" if nonlinear else "LoadCases.DirHistLinear"
        self._g.call(case.SetCase, name, api_name=f"{api_root}.SetCase")
        self._g.call(
            case.SetTimeIntegration,
            name,
            int(integ.method),
            float(integ.alpha),
            float(integ.beta),
            float(integ.gamma),
            float(integ.theta),
            0.0,
            api_name=f"{api_root}.SetTimeIntegration",
        )
        self._g.call(
            case.SetDampProportional,
            name,
            int(damping.kind),
            float(damping.a),
            float(damping.b),
            float(damping.f1),
            float(damping.f2),
            float(damping.d1),
            float(damping.d2),
            api_name=f"{api_root}.SetDampProportional",
        )
        if nonlinear:
            self._g.call(
                case.SetGeometricNonLinearity,
                name,
                int(geometric_nonlinearity),
                api_name=f"{api_root}.SetGeometricNonLinearity",
            )
            if initial_case is not None:
                self._g.call(
                    case.SetInitialCase,
                    name,
                    initial_case,
                    api_name=f"{api_root}.SetInitialCase",
                )
        self._g.call(
            case.SetTimeStep,
            name,
            int(steps),
            float(dt),
            api_name=f"{api_root}.SetTimeStep",
        )
        self._set_history_loads(case, api_root, name, loads)
        return name

    def add_static_nonlinear(
        self,
        name: str,
        *,
        loads: Mapping[str, float],
        initial_case: str | None = None,
        geometric_nonlinearity: GeomNonlinearity = GeomNonlinearity.NONE,
        displacement_control: tuple[PointHandle | str, _DofName, float] | None = None,
        results_saved: _StaticResultsSaved = "final",
    ) -> str:
        """Create a nonlinear static case.

        Wraps ``LoadCases.StaticNonLinear.SetCase``.
        """
        case = self._raw.LoadCases.StaticNonLinear
        self._g.call(case.SetCase, name, api_name="LoadCases.StaticNonLinear.SetCase")
        self._g.call(
            case.SetGeometricNonLinearity,
            name,
            int(geometric_nonlinearity),
            api_name="LoadCases.StaticNonLinear.SetGeometricNonLinearity",
        )
        if initial_case is not None:
            self._g.call(
                case.SetInitialCase,
                name,
                initial_case,
                api_name="LoadCases.StaticNonLinear.SetInitialCase",
            )
        pattern_names = list(loads)
        self._g.call(
            case.SetLoads,
            name,
            len(pattern_names),
            ["Load"] * len(pattern_names),
            pattern_names,
            [float(loads[p]) for p in pattern_names],
            api_name="LoadCases.StaticNonLinear.SetLoads",
        )
        if displacement_control is not None:
            point, dof, displacement = displacement_control
            point_ref = self._model.points.ref(point)
            self._g.call(
                case.SetLoadApplication,
                name,
                2,
                2,
                float(displacement),
                1,
                _DOF_INDEX[dof],
                point_ref.name,
                "",
                api_name="LoadCases.StaticNonLinear.SetLoadApplication",
            )
        if results_saved == "multiple":
            self._g.call(
                case.SetResultsSaved,
                name,
                True,
                10,
                100,
                True,
                api_name="LoadCases.StaticNonLinear.SetResultsSaved",
            )
        return name

    def _set_history_loads(
        self,
        case: object,
        api_root: str,
        name: str,
        loads: Sequence[HistoryLoad],
    ) -> None:
        self._g.call(
            case.SetLoads,  # type: ignore[attr-defined]
            name,
            len(loads),
            ["Accel" if load.kind == "accel" else "Load" for load in loads],
            [load.load for load in loads],
            [_function_name(load.function) for load in loads],
            [float(load.scale) for load in loads],
            [float(load.time_factor) for load in loads],
            [float(load.arrival) for load in loads],
            [load.csys for load in loads],
            [float(load.angle) for load in loads],
            api_name=f"{api_root}.SetLoads",
        )

    def names(self) -> list[str]:
        """All load case names. Wraps ``LoadCases.GetNameList``."""
        _count, names = self._g.call(
            self._raw.LoadCases.GetNameList, api_name="LoadCases.GetNameList"
        )
        return list(names) if names else []


class Loads(Manager[Handle]):
    """Groups the load-pattern and load-case managers under ``model.loads``."""

    def __init__(self, model) -> None:  # type: ignore[no-untyped-def]
        super().__init__(model)
        self.patterns = LoadPatterns(model)
        self.cases = LoadCases(model)

    def set_mass_source(
        self,
        *,
        from_elements: bool = True,
        from_masses: bool = True,
        from_loads: Mapping[str, float] | None = None,
        name: str = "MSSSRC1",
        default: bool = True,
    ) -> None:
        """Define a mass source.

        Wraps ``SourceMass.SetMassSource``.
        """
        load_names = list(from_loads or {})
        self._g.call(
            self._raw.SourceMass.SetMassSource,
            name,
            bool(from_elements),
            bool(from_masses),
            from_loads is not None,
            bool(default),
            len(load_names),
            load_names,
            [float(from_loads[p]) for p in load_names] if from_loads else [],
            api_name="SourceMass.SetMassSource",
        )
