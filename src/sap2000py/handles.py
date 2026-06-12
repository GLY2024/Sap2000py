"""Lightweight, immutable references to model objects.

A handle is a typed wrapper around an object's *name*. It deliberately caches
no model state, so editing the model in the SAP2000 GUI never makes a handle go
stale. Every API that accepts an object accepts ``Handle | str`` and normalizes
internally with :func:`as_name`.

Convenience accessors (e.g. ``point.coordinates``) are attached by the typed
``model`` layer, which sets ``_owner`` to the managing collection when it mints
a handle. ``_owner`` is excluded from equality and repr, so two handles compare
equal iff they have the same type and name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Handle:
    """Base class for all object handles. Stringifies to its name."""

    name: str
    _owner: Any = field(default=None, compare=False, repr=False, kw_only=True)

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class PointHandle(Handle):
    """A point (joint) object."""


@dataclass(frozen=True)
class FrameHandle(Handle):
    """A frame (line) object."""


@dataclass(frozen=True)
class CableHandle(Handle):
    """A cable object."""


@dataclass(frozen=True)
class TendonHandle(Handle):
    """A tendon object."""


@dataclass(frozen=True)
class AreaHandle(Handle):
    """An area (shell) object."""


@dataclass(frozen=True)
class SolidHandle(Handle):
    """A solid object."""


@dataclass(frozen=True)
class LinkHandle(Handle):
    """A link (two-joint or one-joint) object."""


@dataclass(frozen=True)
class MaterialHandle(Handle):
    """A material property."""


@dataclass(frozen=True)
class FrameSectionHandle(Handle):
    """A frame section property."""


@dataclass(frozen=True)
class LinkPropHandle(Handle):
    """A link property (linear or nonlinear)."""


@dataclass(frozen=True)
class GroupHandle(Handle):
    """A named group of objects."""


def as_name(obj: Handle | str) -> str:
    """Return the object's name whether given a handle or a raw string."""
    return obj.name if isinstance(obj, Handle) else obj
