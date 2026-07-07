"""Incremental dynamic analysis driver."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from numpy.typing import NDArray

from .ground_motion import GroundMotionRecord, GroundMotionSuite
from .runner import NlthConfig, _record_im, _run_single_record

if TYPE_CHECKING:
    from ..model import Model
    from .edp import Edp

_IdaIm = Literal["pga", "sa_t1"] | Callable[[GroundMotionRecord], float]


@dataclass(frozen=True)
class IdaCurve:
    """One IDA curve."""

    record: str
    im: NDArray[np.float64]
    edp: NDArray[np.float64]
    collapse_im: float | None


def run_ida(
    model: Model,
    suite: GroundMotionSuite,
    *,
    edp: Edp,
    config: NlthConfig,
    im: _IdaIm = "pga",
    levels: Sequence[float] | None = None,
    hunt: bool = False,
    collapse_edp: float | None = None,
    workdir: Path,
    resume: bool = True,
) -> list[IdaCurve]:
    """Run IDA curves by scaling records to target IM levels."""
    target_levels = (
        np.arange(0.1, 2.0 + 0.05, 0.1, dtype=np.float64)
        if levels is None
        else np.asarray(levels, dtype=np.float64)
    )
    curves: list[IdaCurve] = []
    for record in suite:
        curve_levels = _hunt_levels() if hunt and levels is None else target_levels
        curves.append(
            _run_ida_record(
                model,
                record,
                edp=edp,
                config=config,
                im=im,
                levels=curve_levels,
                collapse_edp=collapse_edp,
                workdir=workdir / record.name,
                resume=resume,
            )
        )
    return curves


def _run_ida_record(
    model: Model,
    record: GroundMotionRecord,
    *,
    edp: Edp,
    config: NlthConfig,
    im: _IdaIm,
    levels: NDArray[np.float64],
    collapse_edp: float | None,
    workdir: Path,
    resume: bool,
) -> IdaCurve:
    base_im = _im_value(record, im)
    if base_im <= 0.0:
        raise ValueError(f"record {record.name!r} has non-positive base IM.")
    im_values: list[float] = []
    edp_values: list[float] = []
    collapse_im: float | None = None
    for level in levels:
        level_value = float(level)
        checkpoint = workdir / f"{record.name}_{level_value:g}.json"
        if resume and checkpoint.exists():
            cached = _read_ida_checkpoint(checkpoint)
            demand = float(cached.edp.get(edp.name, np.nan))
            finished = cached.finished
        else:
            result = _run_single_record(
                model,
                record,
                edps=[edp],
                config=config,
                ims=[] if callable(im) else [_im_name(im)],
                scale=level_value / base_im,
                workdir=workdir,
                on_error="skip",
            )
            demand = float(result.edp.get(edp.name, np.nan))
            finished = result.finished
            _write_ida_checkpoint(
                checkpoint,
                edp.name,
                demand,
                finished,
            )
        im_values.append(level_value)
        edp_values.append(demand)
        collapsed = not finished or (
            collapse_edp is not None and np.isfinite(demand) and demand >= collapse_edp
        )
        if collapsed:
            collapse_im = level_value
            break
    return IdaCurve(
        record=record.name,
        im=np.asarray(im_values, dtype=np.float64),
        edp=np.asarray(edp_values, dtype=np.float64),
        collapse_im=collapse_im,
    )


def _im_value(record: GroundMotionRecord, im: _IdaIm) -> float:
    if callable(im):
        return float(im(record))
    return _record_im(record, im)


def _im_name(im: _IdaIm) -> str:
    return im if isinstance(im, str) else "im"


def _hunt_levels() -> NDArray[np.float64]:
    # ponytail: compact hunt path; fixed-level IDA remains the primary path.
    return np.asarray([0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4], dtype=np.float64)


@dataclass(frozen=True)
class _IdaCheckpoint:
    edp: dict[str, float]
    finished: bool


def _read_ida_checkpoint(path: Path) -> _IdaCheckpoint:
    name, demand, finished = path.read_text(encoding="utf-8").split(",", maxsplit=2)
    return _IdaCheckpoint(edp={name: float(demand)}, finished=bool(int(finished)))


def _write_ida_checkpoint(path: Path, name: str, demand: float, finished: bool) -> None:
    path.write_text(f"{name},{demand:.17g},{int(finished)}", encoding="utf-8")
