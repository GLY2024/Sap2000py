"""Response-spectrum and time-history function definitions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

from ..enums import Chinese2010SeismicIntensity
from ..handles import Handle
from ._base import Manager


@dataclass(frozen=True, eq=False)
class FunctionHandle(Handle):
    """A live function reference."""

    _manager_path: ClassVar[str] = "m.functions"

    def delete(self) -> None:
        """Delete this function."""
        owner = self._require_owner()
        owner._g.call(owner._raw.Func.Delete, self.name, api_name="Func.Delete")


def _floats(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values]


def _with_trailing_provided(args: list[Any], values: Sequence[Any | None]) -> list[Any]:
    last = -1
    for index, value in enumerate(values):
        if value is not None:
            last = index
    args.extend(values[: last + 1])
    return args


class SpectrumFunctions(Manager[FunctionHandle]):
    """Define response-spectrum functions. Reached as ``model.functions.rs``."""

    _handle_cls = FunctionHandle
    _kind = "function"

    def add_jtg_b02_2013(
        self,
        name: str,
        *,
        direction: int,
        peak_accel: float,
        tg: float,
        ci: float,
        cs: float,
        damping: float = 0.05,
    ) -> FunctionHandle:
        """Define a JTG B02-2013 response-spectrum function.

        Wraps ``Func.FuncRS.SetJTGB022013``.
        """
        self._g.call(
            self._raw.Func.FuncRS.SetJTGB022013,
            name,
            int(direction),
            float(peak_accel),
            float(tg),
            float(ci),
            float(cs),
            float(damping),
            api_name="Func.FuncRS.SetJTGB022013",
        )
        return self._handle(name)

    def add_cjj_166_2011(
        self,
        name: str,
        *,
        direction: int,
        peak_accel: float,
        tg: float,
        damping: float = 0.05,
    ) -> FunctionHandle:
        """Define a CJJ 166-2011 response-spectrum function.

        Wraps ``Func.FuncRS.SetCJJ1662011``.
        """
        self._g.call(
            self._raw.Func.FuncRS.SetCJJ1662011,
            name,
            int(direction),
            float(peak_accel),
            float(tg),
            float(damping),
            api_name="Func.FuncRS.SetCJJ1662011",
        )
        return self._handle(name)

    def add_chinese_2010(
        self,
        name: str,
        *,
        alpha_max: float,
        seismic_intensity: Chinese2010SeismicIntensity | int,
        tg: float,
        period_discount_factor: float,
        damping: float = 0.05,
    ) -> FunctionHandle:
        """Define a Chinese 2010 response-spectrum function.

        ``seismic_intensity`` is the CSI/JGJ enum value, not the raw intensity
        number: 1=6(0.05g), 2=7(0.10g), 3=7(0.15g), 4=8(0.20g),
        5=8(0.30g), 6=9(0.40g).

        Wraps ``Func.FuncRS.SetChinese2010``.
        """
        intensity = Chinese2010SeismicIntensity(seismic_intensity)
        self._g.call(
            self._raw.Func.FuncRS.SetChinese2010,
            name,
            float(alpha_max),
            int(intensity),
            float(tg),
            float(period_discount_factor),
            float(damping),
            api_name="Func.FuncRS.SetChinese2010",
        )
        return self._handle(name)

    def add_eurocode8_2004(
        self,
        name: str,
        ground_type: int,
        spectrum_type: int,
        ag: float,
        beta: float | None = None,
        q: float | None = None,
        damping: float | None = None,
    ) -> FunctionHandle:
        """Define an Eurocode 8-2004 response-spectrum function.

        CSI v25 ``cFunctionRS.SetEurocode82004`` order is ``Name,
        EURO2004GroundType, EURO2004SpectrumType, EURO2004Ag, EURO2004Beta,
        EURO2004Q, DampRatio``.

        Wraps ``Func.FuncRS.SetEurocode82004``.
        """
        args = _with_trailing_provided(
            [name, int(ground_type), int(spectrum_type), float(ag)],
            [
                None if beta is None else float(beta),
                None if q is None else float(q),
                None if damping is None else float(damping),
            ],
        )
        self._g.call(
            self._raw.Func.FuncRS.SetEurocode82004,
            *args,
            api_name="Func.FuncRS.SetEurocode82004",
        )
        return self._handle(name)

    def add_user(
        self,
        name: str,
        periods: Sequence[float],
        values: Sequence[float],
        *,
        damping: float = 0.05,
    ) -> FunctionHandle:
        """Define a user response-spectrum function.

        Wraps ``Func.FuncRS.SetUser``.
        """
        if len(periods) != len(values):
            raise ValueError("periods and values must have the same length.")
        self._g.call(
            self._raw.Func.FuncRS.SetUser,
            name,
            len(periods),
            _floats(periods),
            _floats(values),
            float(damping),
            api_name="Func.FuncRS.SetUser",
        )
        return self._handle(name)

    def add_from_file(
        self,
        name: str,
        path: str | Path,
        *,
        head_lines: int = 0,
        damping: float = 0.05,
        values: Literal["period", "frequency"] = "period",
    ) -> FunctionHandle:
        """Define a response-spectrum function from a text file.

        Wraps ``Func.FuncRS.SetFromFile``.
        """
        value_type = {"frequency": 1, "period": 2}[values]
        self._g.call(
            self._raw.Func.FuncRS.SetFromFile,
            name,
            str(path),
            int(head_lines),
            float(damping),
            value_type,
            api_name="Func.FuncRS.SetFromFile",
        )
        return self._handle(name)

    def names(self) -> list[str]:
        """All function names. Wraps ``Func.GetNameList``."""
        return Functions(self._model).names()


class HistoryFunctions(Manager[FunctionHandle]):
    """Define time-history functions. Reached as ``model.functions.th``."""

    _handle_cls = FunctionHandle
    _kind = "function"

    def add_user(
        self,
        name: str,
        times: Sequence[float],
        values: Sequence[float],
    ) -> FunctionHandle:
        """Define a user time-history function.

        Wraps ``Func.FuncTH.SetUser``.
        """
        if len(times) != len(values):
            raise ValueError("times and values must have the same length.")
        self._g.call(
            self._raw.Func.FuncTH.SetUser,
            name,
            len(times),
            _floats(times),
            _floats(values),
            api_name="Func.FuncTH.SetUser",
        )
        return self._handle(name)

    def add_from_file(
        self,
        name: str,
        path: str | Path,
        head_lines: int | None = None,
        prefix_chars: int | None = None,
        points_per_line: int | None = None,
        value_type: int | None = None,
        free_format: bool | None = None,
        number_fixed: int | None = None,
        dt: float | None = None,
    ) -> FunctionHandle:
        """Define a time-history function from a text file.

        CSI v25 order is ``Name, FileName, HeadLines, PreChars,
        PointsPerLine, ValueType, FreeFormat, NumberFixed``; the ``Dt``
        overload is exposed as ``SetFromFile_1``.

        Wraps ``Func.FuncTH.SetFromFile`` or ``Func.FuncTH.SetFromFile_1``.
        """
        args = _with_trailing_provided(
            [name, str(path)],
            [
                None if head_lines is None else int(head_lines),
                None if prefix_chars is None else int(prefix_chars),
                None if points_per_line is None else int(points_per_line),
                None if value_type is None else int(value_type),
                None if free_format is None else bool(free_format),
                None if number_fixed is None else int(number_fixed),
                None if dt is None else float(dt),
            ],
        )
        com_func = (
            self._raw.Func.FuncTH.SetFromFile_1
            if dt is not None
            else self._raw.Func.FuncTH.SetFromFile
        )
        api_name = (
            "Func.FuncTH.SetFromFile_1" if dt is not None else "Func.FuncTH.SetFromFile"
        )
        self._g.call(
            com_func,
            *args,
            api_name=api_name,
        )
        return self._handle(name)

    def names(self) -> list[str]:
        """All function names. Wraps ``Func.GetNameList``."""
        return Functions(self._model).names()


class Functions(Manager[FunctionHandle]):
    """Groups response-spectrum and time-history function managers."""

    _handle_cls = FunctionHandle
    _kind = "function"

    def __init__(self, model) -> None:  # type: ignore[no-untyped-def]
        super().__init__(model)
        self.rs = SpectrumFunctions(model)
        self.th = HistoryFunctions(model)

    def names(self) -> list[str]:
        """All function names.

        Wraps ``Func.GetNameList``.
        """
        _count, names = self._g.call(self._raw.Func.GetNameList, api_name="Func.GetNameList")
        return list(names) if names else []

    def delete(self, name: FunctionHandle | str) -> None:
        """Delete a function.

        Wraps ``Func.Delete``.
        """
        function = self.ref(name)
        self._g.call(self._raw.Func.Delete, function.name, api_name="Func.Delete")
