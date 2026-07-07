"""Ground-motion records and adaptive parsers."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NoReturn

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from ..enums import Units
from ..errors import GroundMotionParseError
from ..model.results import ResultTable

if TYPE_CHECKING:
    from ..model import Model

_G_MPS2 = 9.80665
_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")
_DT = re.compile(r"\bD[TE]\b\s*[:=]?\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?)", re.I)
_NPTS = re.compile(r"\bNPTS\b\s*[:=]?\s*(\d+)", re.I)
_PEER = re.compile(
    r"\bNPTS\b\s*[:=]?\s*(\d+).*?\bD[TE]\b\s*[:=]?\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?)",
    re.I,
)

_Format = Literal["auto", "peer", "columns", "csv"]
_Unit = Literal["g", "gal", "cm/s2", "m/s2"]


def gravity(units: Units) -> float:
    """Return gravitational acceleration in the unit system's length unit/s^2.

    Parameters
    ----------
    units:
        SAP2000 force-length-temperature unit enum.

    Returns
    -------
    float
        ``9.80665`` converted from meters to the enum's length unit.
    """
    length = units.name.split("_")[1]
    factors = {
        "M": 1.0,
        "MM": 1000.0,
        "CM": 100.0,
        "FT": 3.280839895013123,
        "IN": 39.37007874015748,
    }
    return _G_MPS2 * factors[length]


@dataclass(frozen=True)
class GroundMotionRecord:
    """A single acceleration history normalized to units of ``g``.

    Attributes
    ----------
    name:
        Record name.
    dt:
        Uniform time step, in seconds.
    accel:
        Acceleration samples, always in ``g``.
    source:
        Optional source path or label.
    """

    name: str
    dt: float
    accel: NDArray[np.float64]
    source: str | None = None

    def __post_init__(self) -> None:
        accel = np.asarray(self.accel, dtype=np.float64)
        if accel.ndim != 1 or len(accel) == 0:
            raise ValueError("accel must be a non-empty one-dimensional array.")
        if self.dt <= 0:
            raise ValueError("dt must be positive.")
        object.__setattr__(self, "dt", float(self.dt))
        object.__setattr__(self, "accel", accel)

    @property
    def times(self) -> NDArray[np.float64]:
        """Sample times in seconds."""
        return np.arange(self.npts, dtype=np.float64) * self.dt

    @property
    def npts(self) -> int:
        """Number of samples."""
        return int(self.accel.size)

    @property
    def duration(self) -> float:
        """Elapsed duration from first to last sample, in seconds."""
        return (self.npts - 1) * self.dt

    @property
    def pga(self) -> float:
        """Peak ground acceleration in ``g``."""
        return float(np.max(np.abs(self.accel)))

    def pgv(self) -> float:
        """Peak ground velocity in m/s from trapezoidal integration."""
        if self.npts == 1:
            return 0.0
        increments = 0.5 * (self.accel[1:] + self.accel[:-1]) * _G_MPS2 * self.dt
        velocity = np.concatenate(([0.0], np.cumsum(increments)))
        return float(np.max(np.abs(velocity)))

    def scaled(self, factor: float) -> GroundMotionRecord:
        """Return a copy with acceleration multiplied by ``factor``."""
        return GroundMotionRecord(
            name=self.name,
            dt=self.dt,
            accel=self.accel * float(factor),
            source=self.source,
        )

    def to_function(self, model: Model, *, name: str | None = None) -> str:
        """Define the record as a SAP2000 time-history function.

        Values are written in ``g``. The conversion from ``g`` to model length
        units/s^2 belongs in the load-case scale, for example
        ``HistoryLoad.scale = gravity(model.current_units)``.
        """
        function_name = name or self.name
        handle = model.functions.th.add_user(
            function_name, self.times.tolist(), self.accel.tolist()
        )
        return handle.name


@dataclass(frozen=True)
class GroundMotionSuite:
    """A collection of ground-motion records."""

    records: tuple[GroundMotionRecord, ...]

    def __iter__(self) -> Iterator[GroundMotionRecord]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, key: int | str) -> GroundMotionRecord:
        if isinstance(key, int):
            return self.records[key]
        for record in self.records:
            if record.name == key:
                return record
        raise KeyError(key)

    def scaled(self, factor: float) -> GroundMotionSuite:
        """Return a suite with every record scaled by ``factor``."""
        return GroundMotionSuite(tuple(record.scaled(factor) for record in self.records))

    def summary(self) -> ResultTable:
        """Return a small summary table for the suite."""
        return ResultTable(
            {
                "name": tuple(record.name for record in self.records),
                "dt": tuple(record.dt for record in self.records),
                "npts": tuple(record.npts for record in self.records),
                "duration": tuple(record.duration for record in self.records),
                "pga": tuple(record.pga for record in self.records),
            }
        )


@dataclass(frozen=True)
class _Parsed:
    dt: float
    accel: NDArray[np.float64]
    unit: _Unit


def read_record(
    path: str | Path,
    *,
    unit: str | None = None,
    dt: float | None = None,
    fmt: _Format = "auto",
    name: str | None = None,
) -> GroundMotionRecord:
    """Read a ground-motion record from PEER, columns, or CSV text.

    Parameters
    ----------
    path:
        Record file.
    unit:
        Explicit acceleration unit. Supported values are ``"g"``, ``"gal"``,
        ``"cm/s2"``, and ``"m/s2"``. Explicit units override headers.
    dt:
        Time step for single-column or wrapped stream files without a header.
    fmt:
        Parser to use, or ``"auto"`` to try PEER then generic columns/CSV.
    name:
        Optional record name. Defaults to the file stem.

    Raises
    ------
    GroundMotionParseError
        If the file cannot be parsed or units cannot be determined.
    """
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    explicit_unit = _normalize_unit(unit) if unit is not None else None
    attempts: list[str] = []

    if fmt not in {"auto", "peer", "columns", "csv"}:
        raise ValueError("fmt must be 'auto', 'peer', 'columns', or 'csv'.")

    if fmt in {"auto", "peer"}:
        try:
            parsed = _parse_peer(lines, explicit_unit=explicit_unit, dt_override=dt)
            return _record(file_path, parsed, name)
        except GroundMotionParseError as exc:
            attempts.append(f"peer: {exc}")
            if fmt == "peer":
                _raise_parse_error(file_path, lines, attempts)

    if fmt in {"auto", "columns", "csv"}:
        try:
            parsed = _parse_generic(
                lines,
                explicit_unit=explicit_unit,
                dt_override=dt,
                force_csv=fmt == "csv",
            )
            return _record(file_path, parsed, name)
        except GroundMotionParseError as exc:
            attempts.append(f"generic: {exc}")

    _raise_parse_error(file_path, lines, attempts)


def read_suite(
    folder: str | Path, *, pattern: str = "*", **reader_kwargs: Any
) -> GroundMotionSuite:
    """Read all matching files in ``folder`` into a suite."""
    root = Path(folder)
    records = tuple(
        read_record(path, **reader_kwargs) for path in sorted(root.glob(pattern)) if path.is_file()
    )
    return GroundMotionSuite(records)


def _record(path: Path, parsed: _Parsed, name: str | None) -> GroundMotionRecord:
    accel = _convert_to_g(parsed.accel, parsed.unit)
    pga = float(np.max(np.abs(accel)))
    if pga > 3.0 or pga < 0.001:
        logger.warning(
            "ground-motion record {} has PGA {:.6g}g after {} unit conversion",
            path,
            pga,
            parsed.unit,
        )
    return GroundMotionRecord(name=name or path.stem, dt=parsed.dt, accel=accel, source=str(path))


def _parse_peer(
    lines: list[str],
    *,
    explicit_unit: _Unit | None,
    dt_override: float | None,
) -> _Parsed:
    for i, line in enumerate(lines):
        match = _PEER.search(line)
        if match is None:
            continue
        npts = int(match.group(1))
        parsed_dt = float(match.group(2))
        if dt_override is not None and not math.isclose(parsed_dt, dt_override, rel_tol=1e-6):
            raise GroundMotionParseError(
                f"PEER dt {parsed_dt:g} disagrees with dt={dt_override:g}."
            )
        values = _numbers_from_lines(lines[i + 1 :])
        if len(values) < npts:
            raise GroundMotionParseError(
                f"PEER header declares {npts} points but found {len(values)}."
            )
        return _Parsed(
            dt=dt_override or parsed_dt,
            accel=np.asarray(values[:npts], dtype=np.float64),
            unit=explicit_unit or "g",
        )
    raise GroundMotionParseError("no PEER NPTS/DT header found.")


def _parse_generic(
    lines: list[str],
    *,
    explicit_unit: _Unit | None,
    dt_override: float | None,
    force_csv: bool,
) -> _Parsed:
    header, rows = _split_header_rows(lines)
    if not rows:
        raise GroundMotionParseError("no numeric data rows found.")
    unit = explicit_unit or _unit_from_header(header)
    if unit is None:
        raise GroundMotionParseError("no acceleration unit found in arguments or header.")

    npts = _npts_from_header(header)
    header_dt = _dt_from_header(header)
    data = _data_matrix(rows, force_csv=force_csv)
    inferred_dt, accel = _columns_to_record(data, dt_override=dt_override or header_dt)
    if npts is not None and len(accel) != npts:
        raise GroundMotionParseError(f"header NPTS={npts} but parsed {len(accel)} samples.")
    return _Parsed(dt=inferred_dt, accel=accel, unit=unit)


def _split_header_rows(lines: list[str]) -> tuple[list[str], list[str]]:
    header: list[str] = []
    rows: list[str] = []
    started = False
    for raw in lines:
        line = raw.strip()
        if not line:
            if not started:
                header.append(raw)
            continue
        if _numeric_row(line):
            started = True
            rows.append(line)
        elif started:
            raise GroundMotionParseError(f"non-numeric trailing line after data: {line!r}.")
        else:
            header.append(raw)
    return header, rows


def _numeric_row(line: str) -> bool:
    try:
        _parse_row(line)
    except ValueError:
        return False
    return True


def _parse_row(line: str) -> list[float]:
    if "," in line:
        parts = line.split(",")
    elif ";" in line:
        parts = line.split(";")
    elif "\t" in line:
        parts = line.split("\t")
    else:
        parts = line.split()
    values = [part.strip() for part in parts if part.strip()]
    if not values:
        raise ValueError("empty row")
    try:
        return [float(value) for value in values]
    except ValueError as exc:
        raise ValueError("non-numeric row") from exc


def _delimiter(line: str) -> str:
    if "," in line:
        return ","
    if ";" in line:
        return ";"
    if "\t" in line:
        return "\t"
    return " "


def _data_matrix(rows: list[str], *, force_csv: bool) -> NDArray[np.float64]:
    delimiters = {_delimiter(row) for row in rows}
    if force_csv and delimiters - {","}:
        raise GroundMotionParseError("fmt='csv' requires comma-delimited numeric rows.")
    if len(delimiters) > 1:
        shown = ", ".join(repr(delim) for delim in sorted(delimiters))
        raise GroundMotionParseError(f"mixed delimiters detected: {shown}.")
    parsed = [_parse_row(row) for row in rows]
    width = len(parsed[0])
    if any(len(row) != width for row in parsed):
        raise GroundMotionParseError("numeric rows have inconsistent column counts.")
    return np.asarray(parsed, dtype=np.float64)


def _columns_to_record(
    data: NDArray[np.float64],
    *,
    dt_override: float | None,
) -> tuple[float, NDArray[np.float64]]:
    if data.ndim != 2:
        raise GroundMotionParseError("numeric data must be two-dimensional.")
    if data.shape[1] == 1:
        if dt_override is None:
            raise GroundMotionParseError("single-column data needs dt= or a DT header.")
        return _validate_dt(dt_override), data[:, 0].astype(np.float64)

    if data.shape[1] == 2 and _looks_like_time(data[:, 0]):
        times = data[:, 0]
        inferred = float(np.median(np.diff(times)))
        if dt_override is not None and not math.isclose(inferred, dt_override, rel_tol=1e-5):
            raise GroundMotionParseError(
                f"inferred dt {inferred:g} disagrees with dt={dt_override:g}."
            )
        return _validate_dt(inferred), data[:, 1].astype(np.float64)

    if dt_override is None:
        raise GroundMotionParseError("wrapped multi-column data needs dt= or a DT header.")
    return _validate_dt(dt_override), data.reshape(-1).astype(np.float64)


def _looks_like_time(values: NDArray[np.float64]) -> bool:
    if len(values) < 2:
        return False
    diffs = np.diff(values)
    if np.any(diffs <= 0):
        return False
    step = float(np.median(diffs))
    return step > 0 and bool(np.allclose(diffs, step, rtol=1e-4, atol=1e-10))


def _validate_dt(value: float) -> float:
    dt = float(value)
    if dt <= 0:
        raise GroundMotionParseError("dt must be positive.")
    return dt


def _numbers_from_lines(lines: list[str]) -> list[float]:
    values: list[float] = []
    for line in lines:
        values.extend(float(match.group(0)) for match in _NUMBER.finditer(line))
    return values


def _normalize_unit(unit: str | None) -> _Unit:
    if unit is None:
        raise ValueError("unit cannot be None.")
    key = unit.strip().lower().replace("^", "").replace("sec", "s").replace(" ", "")
    aliases: dict[str, _Unit] = {
        "g": "g",
        "gal": "gal",
        "cm/s2": "cm/s2",
        "cm/s/s": "cm/s2",
        "m/s2": "m/s2",
        "m/s/s": "m/s2",
    }
    if key not in aliases:
        raise ValueError("unit must be one of 'g', 'gal', 'cm/s2', or 'm/s2'.")
    return aliases[key]


def _unit_from_header(header: list[str]) -> _Unit | None:
    text = "\n".join(header).lower().replace("^", "")
    if re.search(r"\bgal\b", text):
        return "gal"
    if re.search(r"\bcm\s*/\s*s(?:ec)?2\b|\bcm\s*/\s*s\s*/\s*s\b", text):
        return "cm/s2"
    if re.search(r"(?<!c)\bm\s*/\s*s(?:ec)?2\b|(?<!c)\bm\s*/\s*s\s*/\s*s\b", text):
        return "m/s2"
    if re.search(r"(?<![a-z])g(?![a-z])", text):
        return "g"
    return None


def _dt_from_header(header: list[str]) -> float | None:
    text = "\n".join(header)
    match = _DT.search(text)
    return float(match.group(1)) if match is not None else None


def _npts_from_header(header: list[str]) -> int | None:
    text = "\n".join(header)
    match = _NPTS.search(text)
    return int(match.group(1)) if match is not None else None


def _convert_to_g(values: NDArray[np.float64], unit: _Unit) -> NDArray[np.float64]:
    factors = {"g": 1.0, "gal": 1.0 / 980.665, "cm/s2": 1.0 / 980.665, "m/s2": 1.0 / _G_MPS2}
    return np.asarray(values, dtype=np.float64) * factors[unit]


def _raise_parse_error(path: Path, lines: list[str], attempts: list[str]) -> NoReturn:
    sample = lines[:8]
    payload = {"path": str(path), "sample": sample, "attempts": attempts}
    message = (
        f"could not parse ground-motion record {path}. "
        f"Sample lines: {sample!r}. Attempts: {attempts!r}."
    )
    exc = GroundMotionParseError(message)
    exc.diagnostics = payload  # type: ignore[attr-defined]
    raise exc
