"""Shared base for the typed model managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..gateway import ComGateway
    from . import Model


class Manager:
    """Base class for a sub-API of :class:`~sap2000py.model.Model`.

    Holds the owning model and a direct gateway handle. ``self._raw`` is the
    raw ``cSapModel`` for building COM call targets like
    ``self._raw.PointObj.AddCartesian``.
    """

    def __init__(self, model: Model) -> None:
        self._model = model
        self._g: ComGateway = model.gateway

    @property
    def _raw(self) -> Any:
        return self._g.model
