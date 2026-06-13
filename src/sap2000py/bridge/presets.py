"""Shipped engineering-parameter presets (externalized from code into YAML).

The old code hard-coded bearing stiffnesses and section coefficients inline. They
now live in ``bridge/data/*.yaml`` and are read through these helpers, so tuning
a value never means editing logic. Reading presets needs the ``bridge`` extra
(PyYAML).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ..errors import MissingDependencyError

_BEARINGS = Path(__file__).resolve().parent / "data" / "bearings.yaml"


@lru_cache(maxsize=1)
def _bearing_table() -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised without the extra
        raise MissingDependencyError("bridge bearing presets", "bridge") from exc
    table: dict[str, Any] = yaml.safe_load(_BEARINGS.read_text(encoding="utf-8"))
    return table


def bearing_presets() -> list[str]:
    """Names of all shipped bearing presets."""
    return sorted(_bearing_table())


def bearing_preset(name: str) -> list[float]:
    """Return a named bearing's ``[U1..R3]`` effective stiffness.

    Use the result as ``Bearing(..., stiffness=bearing_preset("pot_fixed"))``.
    """
    table = _bearing_table()
    try:
        entry = table[name]
    except KeyError:
        raise KeyError(f"unknown bearing preset {name!r}; available: {sorted(table)}.") from None
    return [float(k) for k in entry["stiffness"]]
