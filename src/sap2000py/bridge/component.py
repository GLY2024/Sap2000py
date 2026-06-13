"""The component protocol every bridge piece implements.

A :class:`BridgeComponent` is *pure data* until built: constructing one touches
no COM. :meth:`BridgeComponent.build` creates the component's objects in a model
passed in **explicitly** — the deliberate break from the old code's 72 hidden
``Saproject()`` singleton calls — and records named connection points in
:attr:`anchors`, which :func:`~sap2000py.bridge.connect.snap_connect` then ties
to neighbouring components.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..handles import PointHandle

if TYPE_CHECKING:
    from ..model import Model


class BridgeComponent(ABC):
    """Base class for a buildable bridge component.

    Subclasses implement :meth:`_build` and register their connection points via
    :meth:`_set_anchor`. The public :meth:`build` enforces build-once semantics.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._anchors: dict[str, PointHandle] = {}
        self._built = False

    @property
    def built(self) -> bool:
        """Whether :meth:`build` has run."""
        return self._built

    @property
    def anchors(self) -> dict[str, PointHandle]:
        """Named connection points, populated by :meth:`build`."""
        return dict(self._anchors)

    def anchor(self, key: str) -> PointHandle:
        """Return the connection point named ``key`` (only after :meth:`build`)."""
        if not self._built:
            raise RuntimeError(f"{self.name!r} is not built; call build(model) first.")
        try:
            return self._anchors[key]
        except KeyError:
            raise KeyError(
                f"{self.name!r} has no anchor {key!r}; available: {sorted(self._anchors)}."
            ) from None

    def _set_anchor(self, key: str, point: PointHandle) -> None:
        self._anchors[key] = point

    def build(self, model: Model) -> None:
        """Create this component's objects in ``model`` (once)."""
        if self._built:
            raise RuntimeError(f"{self.name!r} is already built.")
        self._build(model)
        self._built = True

    @abstractmethod
    def _build(self, model: Model) -> None:
        """Subclass hook: create objects and register anchors."""
