"""Shared base for the typed model managers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, overload

if TYPE_CHECKING:
    from ..gateway import ComGateway
    from . import Model

from ..errors import SapNameNotFoundError
from ..handles import Handle

H = TypeVar("H", bound=Handle)
T = TypeVar("T")


@overload
def _as_tuple(values: str) -> tuple[str, ...]: ...


@overload
def _as_tuple(values: Iterable[T]) -> tuple[T, ...]: ...


def _as_tuple(values: str | Iterable[T]) -> tuple[str, ...] | tuple[T, ...]:
    return (values,) if isinstance(values, str) else tuple(values)


class Manager(Generic[H]):
    """Base class for a sub-API of :class:`~sap2000py.model.Model`.

    Holds the owning model and a direct gateway handle. ``self._raw`` is the
    raw ``cSapModel`` for building COM call targets like
    ``self._raw.PointObj.AddCartesian``.
    """

    _handle_cls: type[H] | None = None
    _kind = "object"

    def __init__(self, model: Model) -> None:
        self._model = model
        self._g: ComGateway = model.gateway

    @property
    def _raw(self) -> Any:
        return self._g.checked_model

    def _require_handle_cls(self) -> type[H]:
        handle_cls = self._handle_cls
        if handle_cls is None:
            raise TypeError(f"{type(self).__name__} does not define a handle class.")
        return handle_cls

    def _handle(self, name: str) -> H:
        return self._require_handle_cls()(name, _owner=self)

    def names(self) -> list[str]:
        raise NotImplementedError

    def all(self) -> list[H]:
        """Return live handles for all names known to this manager."""
        self._require_handle_cls()
        return [self._handle(name) for name in self.names()]

    def get(self, name: str) -> H:
        """Return a live handle after validating that ``name`` exists."""
        self._require_handle_cls()
        available = self.names()
        if name not in available:
            raise SapNameNotFoundError(name, kind=self._kind, available=available)
        return self._handle(name)

    def __getitem__(self, name: str) -> H:
        return self.get(name)

    def ref(self, obj: H | str) -> H:
        """Normalize ``obj`` to this manager's handle type.

        Raw strings stay unchecked for internal known-good references. Unbound
        typed handles are validated before binding to this manager.
        """
        handle_cls = self._require_handle_cls()
        if isinstance(obj, str):
            return self._handle(obj)
        if not isinstance(obj, Handle):
            raise TypeError(f"expected {handle_cls.__name__} or str, got {type(obj).__name__}.")
        if not isinstance(obj, handle_cls):
            raise TypeError(f"expected {handle_cls.__name__}, got {type(obj).__name__}.")
        if obj._owner is self:
            return obj
        if obj._owner is None:
            return self.get(obj.name)
        raise ValueError(
            f"{type(obj).__name__}({obj.name!r}) belongs to another manager/model; "
            f"pass {type(obj).__name__}.name to rebind explicitly."
        )

    def _checked_ref(self, obj: H | str) -> H:
        """Normalize public inputs, validating raw strings before use."""
        if isinstance(obj, str):
            return self.get(obj)
        return self.ref(obj)
