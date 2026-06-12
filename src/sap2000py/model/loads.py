"""Load patterns, load cases, and combinations.

This collapses the old ``Sapload.py`` (13 near-identical ``load_*`` classes,
~1,300 lines) into two small managers with parameterized methods.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..enums import LoadPatternType
from ._base import Manager


class LoadPatterns(Manager):
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


class LoadCases(Manager):
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

    def add_modal_ritz(self, name: str, *, num_modes: int = 12) -> str:
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
        return name

    def names(self) -> list[str]:
        """All load case names. Wraps ``LoadCases.GetNameList``."""
        _count, names = self._g.call(
            self._raw.LoadCases.GetNameList, api_name="LoadCases.GetNameList"
        )
        return list(names) if names else []


class Loads(Manager):
    """Groups the load-pattern and load-case managers under ``model.loads``."""

    def __init__(self, model) -> None:  # type: ignore[no-untyped-def]
        super().__init__(model)
        self.patterns = LoadPatterns(model)
        self.cases = LoadCases(model)
