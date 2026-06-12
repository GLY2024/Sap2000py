"""The typed domain facade.

``client.model`` is a :class:`Model`. It groups the everyday API into
sub-managers (``files``, ``points``, ...) and owns unit handling. Anything not
yet wrapped here is reachable through ``client.api`` (the full dynamic proxy).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ..enums import Units
from ..gateway import ComGateway
from .files import Files
from .points import Points

__all__ = ["Model"]


class Model:
    """Typed facade over a SAP2000 ``cSapModel``.

    Parameters
    ----------
    gateway:
        The shared :class:`~sap2000py.gateway.ComGateway`.
    """

    def __init__(self, gateway: ComGateway) -> None:
        self._g = gateway
        self.files = Files(self)
        self.points = Points(self)
        # M2 adds: frames, materials, frame_sections, link_props, links,
        # constraints, groups, loads, analysis, results.

    @property
    def gateway(self) -> ComGateway:
        """The call gateway backing this model."""
        return self._g

    @property
    def raw(self) -> Any:
        """The raw comtypes ``cSapModel`` — escape hatch for unwrapped APIs."""
        return self._g.model

    # -- units --------------------------------------------------------------

    @property
    def current_units(self) -> Units:
        """The model's present units. Wraps ``GetPresentUnits``."""
        return Units(self._g.value(self._g.model.GetPresentUnits, api_name="GetPresentUnits"))

    def set_units(self, units: Units) -> None:
        """Set the model's present units. Wraps ``SetPresentUnits``."""
        self._g.call(self._g.model.SetPresentUnits, int(units), api_name="SetPresentUnits")

    @contextmanager
    def units(self, units: Units) -> Iterator[Model]:
        """Temporarily switch units, restoring the previous units on exit.

        This is the only supported way to change units mid-operation, so a
        block can never silently leave the model in the wrong units::

            with model.units(Units.KN_MM_C):
                model.frame_sections.add_general(...)
        """
        previous = self.current_units
        self.set_units(units)
        try:
            yield self
        finally:
            self.set_units(previous)

    @property
    def is_locked(self) -> bool:
        """Whether the model is locked. Wraps ``GetModelIsLocked``."""
        return bool(self._g.value(self._g.model.GetModelIsLocked, api_name="GetModelIsLocked"))

    def set_locked(self, locked: bool) -> None:
        """Lock or unlock the model. Wraps ``SetModelIsLocked``."""
        self._g.call(self._g.model.SetModelIsLocked, locked, api_name="SetModelIsLocked")
