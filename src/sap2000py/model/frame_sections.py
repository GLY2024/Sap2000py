"""Frame section properties: rectangular, circular, and fully general."""

from __future__ import annotations

from collections.abc import Sequence

from ..handles import FrameSectionHandle, MaterialHandle, as_name
from ._base import Manager


class FrameSections(Manager):
    """Define and query frame section properties. Wraps ``cPropFrame``."""

    def _handle(self, name: str) -> FrameSectionHandle:
        return FrameSectionHandle(name, _owner=self)

    def add_rectangle(
        self,
        name: str,
        *,
        material: MaterialHandle | str,
        depth: float,
        width: float,
        notes: str = "",
    ) -> FrameSectionHandle:
        """Add a solid rectangular section (``depth`` = t3, ``width`` = t2).

        Dimensions are in the model's current length unit. Wraps
        ``PropFrame.SetRectangle``.
        """
        self._g.call(
            self._raw.PropFrame.SetRectangle,
            name,
            as_name(material),
            float(depth),
            float(width),
            -1,
            notes,
            "",
            api_name="PropFrame.SetRectangle",
        )
        return self._handle(name)

    def add_circle(
        self,
        name: str,
        *,
        material: MaterialHandle | str,
        diameter: float,
        notes: str = "",
    ) -> FrameSectionHandle:
        """Add a solid circular section. Wraps ``PropFrame.SetCircle``."""
        self._g.call(
            self._raw.PropFrame.SetCircle,
            name,
            as_name(material),
            float(diameter),
            -1,
            notes,
            "",
            api_name="PropFrame.SetCircle",
        )
        return self._handle(name)

    def add_general(
        self,
        name: str,
        *,
        material: MaterialHandle | str,
        depth: float,
        width: float,
        area: float,
        as2: float,
        as3: float,
        torsion: float,
        i22: float,
        i33: float,
        notes: str = "",
    ) -> FrameSectionHandle:
        """Add a general section from explicit section properties.

        ``torsion`` is the torsional constant J; ``i22``/``i33`` the moments of
        inertia; ``as2``/``as3`` the shear areas. All in the current units.
        Wraps ``PropFrame.SetGeneral`` (radii of gyration set to 1, modifiers
        left default).
        """
        self._g.call(
            self._raw.PropFrame.SetGeneral,
            name,
            as_name(material),
            float(depth),
            float(width),
            float(area),
            float(as2),
            float(as3),
            float(torsion),
            float(i22),
            float(i33),
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            -1,
            notes,
            "",
            api_name="PropFrame.SetGeneral",
        )
        return self._handle(name)

    def set_modifiers(self, section: FrameSectionHandle | str, modifiers: Sequence[float]) -> None:
        """Set the 8 section property modifiers.

        Order: ``[area, as2, as3, torsion, i22, i33, mass, weight]``. Wraps
        ``PropFrame.SetModifiers``.
        """
        if len(modifiers) != 8:
            raise ValueError(f"modifiers must have 8 elements, got {len(modifiers)}.")
        self._g.call(
            self._raw.PropFrame.SetModifiers,
            as_name(section),
            list(modifiers),
            api_name="PropFrame.SetModifiers",
        )

    def names(self) -> list[str]:
        """All frame section names. Wraps ``PropFrame.GetNameList``."""
        _count, names = self._g.call(
            self._raw.PropFrame.GetNameList, api_name="PropFrame.GetNameList"
        )
        return list(names) if names else []
