"""Small parametric-study driver."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..enums import Units
from ..model.results import ResultTable

if TYPE_CHECKING:
    from ..client import SapClient
    from ..model import Model


@dataclass(frozen=True)
class ParameterGrid:
    """Cartesian product of named parameter axes.

    Parameters
    ----------
    axes:
        Mapping from parameter name to the ordered values to try.
    """

    axes: Mapping[str, Sequence[Any]]

    def combos(self) -> Iterator[dict[str, Any]]:
        """Yield one parameter dictionary per Cartesian-product combination."""
        keys = tuple(self.axes)
        for values in product(*(self.axes[key] for key in keys)):
            yield dict(zip(keys, values, strict=True))

    def __len__(self) -> int:
        count = 1
        for values in self.axes.values():
            count *= len(values)
        return count


def run_study(
    client: SapClient,
    grid: ParameterGrid | Sequence[Mapping[str, Any]],
    *,
    build: Callable[[Mapping[str, Any], Model], None],
    collect: Callable[[Mapping[str, Any], Model], Mapping[str, float]],
    workdir: Path,
    run_cases: Sequence[str] | None = None,
    resume: bool = True,
    units: Units | None = None,
) -> ResultTable:
    """Run a checkpointed parameter study in one SAP2000 client.

    Parameters
    ----------
    client:
        Active SAP2000 client.
    grid:
        A :class:`ParameterGrid` or explicit sequence of parameter mappings.
    build:
        Callable that mutates a blank model for one parameter set.
    collect:
        Callable that extracts scalar metrics after analysis.
    workdir:
        Study folder; models and ``study.jsonl`` are written here.
    run_cases:
        Optional load cases passed to ``model.analysis.run``.
    resume:
        When true, completed parameter hashes are loaded from ``study.jsonl``.
    units:
        Optional database units passed to ``model.files.new_blank`` before
        ``build`` is called.

    Returns
    -------
    ResultTable
        One row per parameter combination, with parameter columns followed by
        collected metric columns.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint = workdir / "study.jsonl"
    completed = _read_checkpoint(checkpoint) if resume else {}
    rows: list[dict[str, Any]] = []

    for params in _combos(grid):
        key = _params_hash(params)
        if resume and key in completed:
            rows.append(completed[key])
            continue

        model = client.model
        model.files.new_blank(units=units)
        build(params, model)
        model.files.save(workdir / f"case_{key}.sdb")
        model.analysis.run(cases=run_cases)
        metrics = collect(params, model)
        row = {**dict(params), **dict(metrics)}
        _append_checkpoint(checkpoint, key, row)
        rows.append(row)

    return _table(rows)


def _combos(grid: ParameterGrid | Sequence[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    if isinstance(grid, ParameterGrid):
        yield from grid.combos()
        return
    for params in grid:
        yield dict(params)


def _params_hash(params: Mapping[str, Any]) -> str:
    payload = repr(tuple(sorted(params.items()))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _read_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        completed[str(item["key"])] = dict(item["row"])
    return completed


def _append_checkpoint(path: Path, key: str, row: Mapping[str, Any]) -> None:
    payload = {"key": key, "row": dict(row)}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload) + "\n")


def _table(rows: Sequence[Mapping[str, Any]]) -> ResultTable:
    if not rows:
        return ResultTable({})
    columns = list(rows[0])
    return ResultTable({name: tuple(row.get(name) for row in rows) for name in columns})
