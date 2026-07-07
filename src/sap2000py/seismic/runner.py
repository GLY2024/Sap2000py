"""Nonlinear time-history batch runners."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..enums import GeomNonlinearity, HistoryOutputOption
from ..errors import SapAnalysisError, SapApiError
from ..model.loads import HistoryLoad, RayleighDamping, TimeIntegration
from .ground_motion import GroundMotionRecord, GroundMotionSuite, gravity
from .spectra import IM_REGISTRY

if TYPE_CHECKING:
    from ..model import Model
    from .edp import Edp

_Method = Literal["direct", "fna"]
_OnError = Literal["skip", "raise"]
_ImSpec = str | Callable[[GroundMotionRecord], float]


@dataclass(frozen=True)
class NlthConfig:
    """Nonlinear time-history case configuration."""

    directions: Mapping[str, float] = field(default_factory=lambda: {"U1": 1.0})
    method: _Method = "direct"
    damping: RayleighDamping | float = 0.05
    integration: TimeIntegration = field(default_factory=TimeIntegration.hht)
    geometric_nonlinearity: GeomNonlinearity = GeomNonlinearity.NONE
    modal_case: str = "MODAL"
    gravity_case: str | None = None
    extra_time: float = 0.0


@dataclass(frozen=True)
class NlthResult:
    """Result row for one record and scale."""

    record: str
    case: str
    scale: float
    im: Mapping[str, float]
    edp: Mapping[str, float]
    finished: bool
    error: str | None = None


def run_nlth_batch(
    model: Model,
    suite: GroundMotionSuite,
    *,
    edps: Sequence[Edp],
    config: NlthConfig,
    ims: Sequence[_ImSpec] = ("pga",),
    scale: float | Mapping[str, float] = 1.0,
    workdir: Path,
    resume: bool = True,
    on_error: _OnError = "skip",
) -> list[NlthResult]:
    """Run one NLTH case per record with checkpoint/resume support."""
    _validate_im_specs(ims)
    workdir.mkdir(parents=True, exist_ok=True)
    results: list[NlthResult] = []
    for record in suite:
        checkpoint = workdir / f"{record.name}.json"
        if resume and checkpoint.exists():
            results.append(_read_checkpoint(checkpoint))
            continue
        factor = _scale_for(record, scale)
        result = _run_single_record(
            model,
            record,
            edps=edps,
            config=config,
            ims=ims,
            scale=factor,
            workdir=workdir,
            on_error=on_error,
        )
        results.append(result)
    return results


def run_msa(
    model: Model,
    stripes: Sequence[tuple[float, GroundMotionSuite]],
    *,
    edps: Sequence[Edp],
    config: NlthConfig,
    workdir: Path,
    target_im: _ImSpec = "pga",
    resume: bool = True,
) -> list[NlthResult]:
    """Run MSA stripes by scaling each record to the requested IM level."""
    _validate_im_specs((target_im,))
    results: list[NlthResult] = []
    for level, suite in stripes:
        scales = {
            record.name: float(level) / _record_im(record, target_im)
            for record in suite
        }
        results.extend(
            run_nlth_batch(
                model,
                suite,
                edps=edps,
                config=config,
                ims=(target_im,),
                scale=scales,
                workdir=workdir / f"stripe_{level:g}",
                resume=resume,
            )
        )
    return results


def _run_single_record(
    model: Model,
    record: GroundMotionRecord,
    *,
    edps: Sequence[Edp],
    config: NlthConfig,
    ims: Sequence[_ImSpec],
    scale: float,
    workdir: Path,
    on_error: _OnError = "skip",
) -> NlthResult:
    """Run one record and extract results before any future unlock."""
    workdir.mkdir(parents=True, exist_ok=True)
    case = f"__nlth_{record.name}"
    try:
        model.set_locked(False)
        _delete_existing(model, case)
        function = record.to_function(model, name=case)
        loads = [
            HistoryLoad(
                function=function,
                load=direction,
                scale=float(direction_factor) * float(scale) * gravity(model.current_units),
            )
            for direction, direction_factor in config.directions.items()
        ]
        steps = record.npts + round(config.extra_time / record.dt)
        if config.method == "fna":
            model.loads.cases.add_modal_history(
                case,
                loads=loads,
                steps=steps,
                dt=record.dt,
                modal_case=config.modal_case,
                damping=_modal_damping(config.damping),
                initial_case=config.gravity_case,
            )
            model.results.set_modal_history_output(HistoryOutputOption.STEP_BY_STEP)
        else:
            model.loads.cases.add_direct_history(
                case,
                loads=loads,
                steps=steps,
                dt=record.dt,
                damping=_direct_damping(config.damping),
                integration=config.integration,
                initial_case=config.gravity_case,
                geometric_nonlinearity=config.geometric_nonlinearity,
            )
            model.results.set_direct_history_output(HistoryOutputOption.STEP_BY_STEP)
        run_cases = _run_cases(config, case)
        model.analysis.run(cases=run_cases)
        model.results.select_output(cases=[case])
        scaled_record = record.scaled(scale)
        im_values = _im_values(scaled_record, ims)
        edp_values = {edp.name: edp.extract(model, case) for edp in edps}
        result = NlthResult(
            record=record.name,
            case=case,
            scale=float(scale),
            im=im_values,
            edp=edp_values,
            finished=True,
        )
        _write_result(workdir, result, checkpoint=True)
        return result
    except (SapAnalysisError, SapApiError) as exc:
        if on_error == "raise":
            raise
        result = NlthResult(
            record=record.name,
            case=case,
            scale=float(scale),
            im={},
            edp={},
            finished=False,
            error=str(exc),
        )
        _write_result(workdir, result, checkpoint=False)
        return result


def _delete_existing(model: Model, case: str) -> None:
    for func, api_name in (
        (model.raw.LoadCases.Delete, "LoadCases.Delete"),
        (model.raw.Func.Delete, "Func.Delete"),
    ):
        with suppress(SapApiError):
            model.gateway.call(func, case, api_name=api_name)


def _direct_damping(damping: RayleighDamping | float) -> RayleighDamping:
    if isinstance(damping, RayleighDamping):
        return damping
    # ponytail: S1 exposes only proportional damping for direct history; callers
    # needing calibrated direct damping should pass RayleighDamping explicitly.
    return RayleighDamping.from_coefficients(0.0, 0.0)


def _modal_damping(damping: RayleighDamping | float) -> float:
    if isinstance(damping, RayleighDamping):
        raise TypeError("method='fna' requires scalar modal damping.")
    return float(damping)


def _run_cases(config: NlthConfig, case: str) -> list[str]:
    cases: list[str] = []
    if config.gravity_case is not None:
        cases.append(config.gravity_case)
    if config.method == "fna":
        cases.append(config.modal_case)
    cases.append(case)
    return list(dict.fromkeys(cases))


def _scale_for(record: GroundMotionRecord, scale: float | Mapping[str, float]) -> float:
    if isinstance(scale, Mapping):
        return float(scale[record.name])
    return float(scale)


def _validate_im_specs(ims: Sequence[_ImSpec]) -> None:
    for spec in ims:
        if spec == "sa_avg":
            raise ValueError(
                "IM 'sa_avg' requires a periods band; pass a bound callable such as "
                "intensity_measure('sa_avg', periods=[...]) or "
                "lambda record: sa_avg(record, periods=[...])."
            )


def _record_im(record: GroundMotionRecord, spec: _ImSpec) -> float:
    if callable(spec):
        return float(spec(record))
    name = spec
    if name == "sa_t1":
        # ponytail: parameterized Sa(T1) needs an explicit callable in IDA for
        # project-specific periods; the string shorthand uses T1=1.0 s.
        return float(IM_REGISTRY[name](record, period=1.0))
    if name == "sa_avg":
        _validate_im_specs((name,))
    return float(IM_REGISTRY[name](record))


def _im_values(record: GroundMotionRecord, ims: Sequence[_ImSpec]) -> dict[str, float]:
    values: dict[str, float] = {}
    for spec in ims:
        key = _im_key(spec)
        # ponytail: duplicate callable labels get a stable numeric suffix.
        if key in values:
            base = key
            suffix = 2
            while f"{base}_{suffix}" in values:
                suffix += 1
            key = f"{base}_{suffix}"
        values[key] = _record_im(record, spec)
    return values


def _im_key(spec: _ImSpec) -> str:
    if isinstance(spec, str):
        return spec
    name = getattr(spec, "__name__", "")
    return name if name and not name.startswith("<") else "im"


def _write_result(workdir: Path, result: NlthResult, *, checkpoint: bool) -> None:
    payload = _result_payload(result)
    if checkpoint:
        (workdir / f"{result.record}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    with (workdir / "results.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_checkpoint(path: Path) -> NlthResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return NlthResult(
        record=str(payload["record"]),
        case=str(payload["case"]),
        scale=float(payload["scale"]),
        im={str(k): float(v) for k, v in dict(payload["im"]).items()},
        edp={str(k): float(v) for k, v in dict(payload["edp"]).items()},
        finished=bool(payload["finished"]),
        error=None if payload.get("error") is None else str(payload["error"]),
    )


def _result_payload(result: NlthResult) -> dict[str, Any]:
    return asdict(result)
