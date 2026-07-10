"""Lightweight name handles.

The concrete live handles for wrapped model nouns live next to their managers
in ``sap2000py.model``. They are live references to SAP2000 objects: a handle
only stores the object's name and never caches model state, while methods on an
owned handle round-trip to SAP2000 each time.

This module stays pure: the base :class:`Handle`, :func:`as_name`, and the
unwrapped name handles for nouns that do not yet have managers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True)
class Handle:
    """Base class for all object handles. Comparison ignores model binding."""

    name: str
    _owner: Any = field(default=None, compare=False, repr=False, kw_only=True)
    _manager_path: ClassVar[str] = "manager"

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Handle) or other.__class__ is not self.__class__:
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        return hash((type(self), self.name))

    def _require_owner(self) -> Any:
        """Return the manager this handle is bound to, or raise a clear error."""
        if self._owner is None:
            hint = f"{self._manager_path}.ref({self.name!r})"
            raise ValueError(
                f"{type(self).__name__}({self.name!r}) is not bound to a model; "
                f"use {hint} or {self._manager_path}[{self.name!r}] before calling live methods."
            )
        return self._owner


@dataclass(frozen=True, eq=False)
class CableHandle(Handle):
    """A cable object."""


@dataclass(frozen=True, eq=False)
class TendonHandle(Handle):
    """A tendon object."""


@dataclass(frozen=True, eq=False)
class AreaHandle(Handle):
    """An area (shell) object."""


@dataclass(frozen=True, eq=False)
class SolidHandle(Handle):
    """A solid object."""


def as_name(obj: Handle | str) -> str:
    """Return the object's name whether given a handle or a raw string."""
    return obj.name if isinstance(obj, Handle) else obj
