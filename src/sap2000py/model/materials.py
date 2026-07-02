"""Material properties: code-based and explicit isotropic materials.

The convenience methods (:meth:`Materials.add_concrete`, :meth:`add_steel`)
port the Chinese-code material knowledge from the old ``Common_Material_Set``
script into the typed API. For grades they don't cover, use :meth:`Materials.add`
with the exact SAP2000 grade string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ..enums import MatType
from ..handles import Handle
from ._base import Manager

# SAP2000 grade-string conventions, ported from the legacy China material set.
_CONCRETE_GRADE = {
    "GB": "GB 50010 {g}",
    "JTG": "JTG D62-2004 {g}",
    "TB": "TB10002.3 {g}",
}
_STEEL_GRADE = {
    "GB": "{g}",  # e.g. "Q345"
    "JTG": "GB/T 714-2008 {g}",  # bridge steel, e.g. "Q345q"
}


@dataclass(frozen=True)
class MaterialHandle(Handle):
    """A live material property reference."""

    _manager_path: ClassVar[str] = "m.materials"

    def set_weight_per_volume(self, value: float) -> MaterialHandle:
        """Set weight per unit volume and return ``self`` for chaining."""
        owner = self._require_owner()
        owner._g.call(
            owner._raw.PropMaterial.SetWeightAndMass,
            self.name,
            1,
            float(value),
            api_name="PropMaterial.SetWeightAndMass",
        )
        return self

    def delete(self) -> None:
        """Delete this material property."""
        owner = self._require_owner()
        owner._g.call(owner._raw.PropMaterial.Delete, self.name, api_name="PropMaterial.Delete")


class Materials(Manager[MaterialHandle]):
    """Define and query material properties. Wraps ``cPropMaterial``."""

    _handle_cls = MaterialHandle
    _kind = "material"

    def add(
        self,
        name: str,
        mat_type: MatType,
        *,
        grade: str,
        region: str = "China",
        standard: str = "GB",
    ) -> MaterialHandle:
        """Add a code-based standard material and rename it to ``name``.

        ``grade`` is the exact SAP2000 grade string (e.g. ``"GB 50010 C40"``).
        Wraps ``PropMaterial.AddMaterial`` + ``ChangeName``.
        """
        assigned = self._g.call(
            self._raw.PropMaterial.AddMaterial,
            "",
            int(mat_type),
            region,
            standard,
            grade,
            api_name="PropMaterial.AddMaterial",
        )
        if name and name != assigned:
            self._g.call(
                self._raw.PropMaterial.ChangeName,
                assigned,
                name,
                api_name="PropMaterial.ChangeName",
            )
            assigned = name
        return self._handle(assigned)

    def add_concrete(
        self,
        name: str,
        *,
        grade: str = "C40",
        code: str = "JTG",
        region: str = "China",
    ) -> MaterialHandle:
        """Add a Chinese-code concrete (``code`` in ``{"GB", "JTG", "TB"}``)."""
        grade_string = _CONCRETE_GRADE[code].format(g=grade)
        return self.add(name, MatType.CONCRETE, grade=grade_string, region=region, standard=code)

    def add_steel(
        self,
        name: str,
        *,
        grade: str = "Q345",
        code: str = "GB",
        region: str = "China",
    ) -> MaterialHandle:
        """Add a Chinese-code structural steel (``code`` in ``{"GB", "JTG"}``)."""
        grade_string = _STEEL_GRADE[code].format(g=grade)
        return self.add(name, MatType.STEEL, grade=grade_string, region=region, standard=code)

    def add_isotropic(
        self,
        name: str,
        *,
        modulus: float,
        poisson: float,
        thermal_coeff: float = 0.0,
        weight_per_volume: float | None = None,
        mat_type: MatType = MatType.STEEL,
    ) -> MaterialHandle:
        """Define a user isotropic material from explicit mechanical properties.

        Wraps ``SetMaterial`` + ``SetMPIsotropic`` (+ ``SetWeightAndMass``).
        Values are in the model's current units.
        """
        self._g.call(
            self._raw.PropMaterial.SetMaterial,
            name,
            int(mat_type),
            api_name="PropMaterial.SetMaterial",
        )
        self._g.call(
            self._raw.PropMaterial.SetMPIsotropic,
            name,
            float(modulus),
            float(poisson),
            float(thermal_coeff),
            api_name="PropMaterial.SetMPIsotropic",
        )
        if weight_per_volume is not None:
            self._g.call(
                self._raw.PropMaterial.SetWeightAndMass,
                name,
                1,  # 1 = weight per unit volume
                float(weight_per_volume),
                api_name="PropMaterial.SetWeightAndMass",
            )
        return self._handle(name)

    def names(self) -> list[str]:
        """All material names. Wraps ``PropMaterial.GetNameList``."""
        _count, names = self._g.call(
            self._raw.PropMaterial.GetNameList, api_name="PropMaterial.GetNameList"
        )
        return list(names) if names else []
