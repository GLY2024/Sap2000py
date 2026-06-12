"""Helper for guarding optional-dependency imports.

Optional feature modules (``sections``, ``fiber``, ...) call :func:`require`
at import time so a missing extra produces a clear, actionable error instead of
a bare ``ModuleNotFoundError``.
"""

from __future__ import annotations

import importlib

from .errors import MissingDependencyError


def require(module: str, *, feature: str, extra: str) -> object:
    """Import and return ``module``, or raise :class:`MissingDependencyError`.

    Parameters
    ----------
    module:
        The importable module name to require, e.g. ``"sectionproperties"``.
    feature:
        Human-readable feature description for the error message.
    extra:
        The pip extra that provides the dependency, e.g. ``"sections"``.
    """
    try:
        return importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise MissingDependencyError(feature, extra) from exc
