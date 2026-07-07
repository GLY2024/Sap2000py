"""Plastic hinge definition and assignment through interactive database tables.

SAP2000 exposes ``FrameObj.GetHingeAssigns`` but no typed ``SetHinge`` method in
the generated v25 OAPI stub, so definitions and assignments are written through
``DatabaseTables.SetTableForEditingArray``.

Assumed v25-unverified table prefixes, confirmed by the ``--sap`` round-trip
test:

* ``Hinges Def 02 - Noninteracting - Deform Control - Moment M3``
* ``Frame Hinge Assigns 01``
* ``Frame Hinge Assigns 02 - Auto Fiber`` for the native fiber feasibility path
* ``Hinge State`` for display-only hinge state results

Assumed field names are resolved at runtime from explicit aliases, including
``Hinge``/``Hinge Name``/``Name``, ``Frame``/``Frame Name``, ``Point``,
``Plastic Rotation``/``Rotation``, ``M/My``/``Moment Ratio``, ``My``/``Yield
Moment``, ``RelDist``/``Relative Distance``, and optional ``IO``/``LS``/``CP``
acceptance columns.

Fiber-hinge feasibility: go/no-go is deliberately deferred to the v25 ``--sap``
round trip. This adapter attempts the native table route; if the required table
or fields are absent it raises ``SapTableSchemaError`` with a manual-template
fallback message. The MC-to-user-hinge route remains the supported general path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..errors import SapTableSchemaError
from ..handles import Handle
from ._base import Manager
from .results import ResultTable

_MOMENT_M3_PREFIX = "Hinges Def 02 - Noninteracting - Deform Control - Moment M3"
_ASSIGN_PREFIX = "Frame Hinge Assigns 01"
_AUTO_FIBER_PREFIX = "Frame Hinge Assigns 02 - Auto Fiber"
_STATE_PREFIX = "Hinge State"
_FIBER_FALLBACK = (
    "Native fiber hinge assignment could not be mapped from the discovered "
    "SAP2000 database-table schema. In SAP2000 v25, create one manual "
    "P-M2-M3 fiber-hinge assignment in the UI, export the interactive database "
    "tables, and use that exported table as the version-specific template."
)


@dataclass(frozen=True)
class MomentHinge:
    """Moment-M3 user hinge definition."""

    name: str
    yield_moment: float
    backbone: Sequence[tuple[float, float]]
    acceptance: tuple[float, float, float] | None = None
    symmetric: bool = True


@dataclass(frozen=True)
class HingeAssign:
    """A frame hinge assignment returned by SAP2000."""

    frame: str
    hinge: str
    rel_dist: float


def _norm(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "hinge": ("Hinge", "Hinge Name", "Name", "HingeName"),
    "frame": ("Frame", "Frame Name", "Object", "FrameName", "Object Name"),
    "point": ("Point", "Hinge Point", "Point ID", "PointID", "Label"),
    "rotation": ("Plastic Rotation", "Rotation", "Rot", "ThetaP", "PlasticRot"),
    "moment_ratio": ("M/My", "Moment Ratio", "Moment/My", "MOverMy", "MomentRatio"),
    "yield_moment": ("My", "M_y", "Yield Moment", "YieldMoment"),
    "rel_dist": ("RelDist", "Relative Distance", "RelativeDist", "Location", "RD"),
    "symmetric": ("Symmetric", "Is Symmetric", "Sym"),
    "io": ("IO", "Immediate Occupancy"),
    "ls": ("LS", "Life Safety"),
    "cp": ("CP", "Collapse Prevention"),
    "hinge_type": ("Hinge Type", "Type", "HingeType"),
    "hinge_length": ("Hinge Length", "Length", "HingeLength"),
}

_WIDE_POINT_FIELDS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "B": (
        ("rotation", ("B Rotation", "B Rot", "BThetaP", "B Plastic Rotation")),
        ("moment_ratio", ("B M/My", "B Moment Ratio", "BMOverMy", "B Moment/My")),
    ),
    "C": (
        ("rotation", ("C Rotation", "C Rot", "CThetaP", "C Plastic Rotation")),
        ("moment_ratio", ("C M/My", "C Moment Ratio", "CMOverMy", "C Moment/My")),
    ),
    "D": (
        ("rotation", ("D Rotation", "D Rot", "DThetaP", "D Plastic Rotation")),
        ("moment_ratio", ("D M/My", "D Moment Ratio", "DMOverMy", "D Moment/My")),
    ),
    "E": (
        ("rotation", ("E Rotation", "E Rot", "EThetaP", "E Plastic Rotation")),
        ("moment_ratio", ("E M/My", "E Moment Ratio", "EMOverMy", "E Moment/My")),
    ),
}


class Hinges(Manager[Handle]):
    """Define, assign, and inspect frame hinges via SAP2000 tables."""

    def define_moment_m3(self, hinge: MomentHinge) -> str:
        """Define a Moment-M3 user hinge.

        Wraps ``DatabaseTables.SetTableForEditingArray``.
        """
        self._require_unlocked()
        if not hinge.backbone:
            raise ValueError("hinge.backbone cannot be empty.")
        table_key = self._find_table(_MOMENT_M3_PREFIX)
        fields = self._field_lookup(table_key)
        if self._has_long_moment_schema(fields):
            columns = self._moment_columns_long(table_key, fields, hinge)
        else:
            columns = self._moment_columns_wide(table_key, fields, hinge)
        self._model.database_tables.edit(table_key, columns)
        self._model.database_tables.apply()
        return hinge.name

    def assign(self, frame: str, hinge: str, *, rel_dist: float) -> None:
        """Assign a hinge to a frame at a relative distance.

        Wraps ``DatabaseTables.SetTableForEditingArray``.
        """
        self._require_unlocked()
        table_key = self._find_table(_ASSIGN_PREFIX)
        fields = self._require_fields(table_key, ("frame", "hinge", "rel_dist"))
        columns: dict[str, Sequence[Any]] = {
            fields["frame"]: [frame],
            fields["hinge"]: [hinge],
            fields["rel_dist"]: [float(rel_dist)],
        }
        self._model.database_tables.edit(table_key, columns)
        self._model.database_tables.apply()

    def assigned(self, frame: str) -> list[HingeAssign]:
        """Return hinge assignments for one frame.

        Wraps ``FrameObj.GetHingeAssigns``.
        """
        result = self._g.call(
            self._raw.FrameObj.GetHingeAssigns,
            frame,
            api_name="FrameObj.GetHingeAssigns",
        )
        return _parse_hinge_assigns(frame, result)

    def states(self, *, group: str = "All") -> ResultTable:
        """Return the hinge-state display table.

        Wraps ``DatabaseTables.GetTableForDisplayArray``.
        """
        table_key = self._find_table(_STATE_PREFIX)
        return self._model.database_tables.get(table_key, group=group)

    def assign_auto_fiber(self, frame: str, *, rel_dist: float, hinge_length: float) -> None:
        """Attempt native SAP2000 P-M2-M3 fiber-hinge assignment through tables.

        Wraps ``DatabaseTables.SetTableForEditingArray``.
        """
        self._require_unlocked()
        try:
            table_key = self._find_table(_AUTO_FIBER_PREFIX)
            fields = self._require_fields(
                table_key,
                ("frame", "rel_dist", "hinge_type", "hinge_length"),
            )
        except SapTableSchemaError as exc:
            raise SapTableSchemaError(f"{exc}\n{_FIBER_FALLBACK}") from exc
        columns: dict[str, Sequence[Any]] = {
            fields["frame"]: [frame],
            fields["rel_dist"]: [float(rel_dist)],
            fields["hinge_type"]: ["Fiber P-M2-M3"],
            fields["hinge_length"]: [float(hinge_length)],
        }
        self._model.database_tables.edit(table_key, columns)
        self._model.database_tables.apply()

    def _require_unlocked(self) -> None:
        if self._model.is_locked:
            raise RuntimeError("model must be unlocked before defining or assigning hinges.")

    def _find_table(self, prefix: str) -> str:
        available = self._model.database_tables.available()
        prefix_norm = prefix.casefold()
        matches = [key for key in available if key.casefold().startswith(prefix_norm)]
        if len(matches) == 1:
            return matches[0]
        exact = [key for key in matches if key.casefold() == prefix_norm]
        if len(exact) == 1:
            return exact[0]
        if matches:
            raise SapTableSchemaError(
                f"Ambiguous SAP2000 database table prefix {prefix!r}. "
                f"Candidates: {matches!r}"
            )
        raise SapTableSchemaError(
            f"No SAP2000 database table starts with {prefix!r}. "
            f"Discovered tables: {available!r}"
        )

    def _field_lookup(self, table_key: str) -> dict[str, str]:
        table = self._model.database_tables.fields(table_key)
        lookup: dict[str, str] = {}
        for row in table.rows():
            key = str(row["field_key"])
            lookup[_norm(key)] = key
            lookup[_norm(str(row["field_name"]))] = key
        return lookup

    def _require_fields(self, table_key: str, needed: Sequence[str]) -> dict[str, str]:
        lookup = self._field_lookup(table_key)
        resolved: dict[str, str] = {}
        missing: list[str] = []
        for logical in needed:
            field = _resolve_field(lookup, _FIELD_ALIASES[logical])
            if field is None:
                missing.append(logical)
            else:
                resolved[logical] = field
        if missing:
            raise SapTableSchemaError(
                f"Table {table_key!r} is missing logical fields {missing!r}. "
                f"Discovered schema: {self._schema_rows(table_key)!r}"
            )
        return resolved

    def _has_long_moment_schema(self, lookup: Mapping[str, str]) -> bool:
        return all(
            _resolve_field(lookup, _FIELD_ALIASES[logical]) is not None
            for logical in ("hinge", "point", "rotation", "moment_ratio", "yield_moment")
        )

    def _moment_columns_long(
        self,
        table_key: str,
        lookup: Mapping[str, str],
        hinge: MomentHinge,
    ) -> dict[str, list[Any]]:
        fields = self._require_fields(
            table_key,
            ("hinge", "point", "rotation", "moment_ratio", "yield_moment"),
        )
        labels = _point_labels(len(hinge.backbone))
        columns: dict[str, list[Any]] = {
            fields["hinge"]: [hinge.name] * len(labels),
            fields["point"]: labels,
            fields["rotation"]: [float(point[0]) for point in hinge.backbone],
            fields["moment_ratio"]: [float(point[1]) for point in hinge.backbone],
            fields["yield_moment"]: [float(hinge.yield_moment)] * len(labels),
        }
        self._append_optional_common(columns, lookup, hinge, len(labels))
        return columns

    def _moment_columns_wide(
        self,
        table_key: str,
        lookup: Mapping[str, str],
        hinge: MomentHinge,
    ) -> dict[str, list[Any]]:
        if len(hinge.backbone) > len(_WIDE_POINT_FIELDS):
            raise ValueError("wide hinge tables support at most B..E backbone points.")
        fields = self._require_fields(table_key, ("hinge", "yield_moment"))
        columns: dict[str, list[Any]] = {
            fields["hinge"]: [hinge.name],
            fields["yield_moment"]: [float(hinge.yield_moment)],
        }
        for label, point in zip(_point_labels(len(hinge.backbone)), hinge.backbone, strict=True):
            for logical, aliases in _WIDE_POINT_FIELDS[label]:
                field = _resolve_field(lookup, aliases)
                if field is None:
                    raise SapTableSchemaError(
                        f"Table {table_key!r} is missing {label} {logical!r}. "
                        f"Discovered schema: {self._schema_rows(table_key)!r}"
                    )
                columns[field] = [float(point[0] if logical == "rotation" else point[1])]
        self._append_optional_common(columns, lookup, hinge, 1)
        return columns

    def _append_optional_common(
        self,
        columns: dict[str, list[Any]],
        lookup: Mapping[str, str],
        hinge: MomentHinge,
        n_rows: int,
    ) -> None:
        symmetric = _resolve_field(lookup, _FIELD_ALIASES["symmetric"])
        if symmetric is not None:
            columns[symmetric] = [hinge.symmetric] * n_rows
        if hinge.acceptance is None:
            return
        for logical, value in zip(("io", "ls", "cp"), hinge.acceptance, strict=True):
            field = _resolve_field(lookup, _FIELD_ALIASES[logical])
            if field is not None:
                columns[field] = [float(value)] * n_rows

    def _schema_rows(self, table_key: str) -> list[dict[str, Any]]:
        return self._model.database_tables.fields(table_key).rows()

    def names(self) -> list[str]:
        """Hinge names are table-backed and not separately enumerable."""
        return []


def _resolve_field(lookup: Mapping[str, str], aliases: Sequence[str]) -> str | None:
    for alias in aliases:
        field = lookup.get(_norm(alias))
        if field is not None:
            return field
    return None


def _point_labels(count: int) -> list[str]:
    labels = ["B", "C", "D", "E"]
    if count > len(labels):
        raise ValueError("moment hinge backbone supports B..E points.")
    return labels[:count]


def _parse_hinge_assigns(frame: str, result: Any) -> list[HingeAssign]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise SapTableSchemaError(f"Unexpected FrameObj.GetHingeAssigns result: {result!r}")
    count = int(result[0])
    sequences = [value for value in result[1:] if isinstance(value, (list, tuple))]
    name_seq = next(
        (
            value
            for value in sequences
            if len(value) == count and all(isinstance(item, str) for item in value)
        ),
        None,
    )
    rel_seq = next(
        (
            value
            for value in reversed(sequences)
            if len(value) == count
            and all(isinstance(item, int | float) and 0.0 <= float(item) <= 1.0 for item in value)
        ),
        None,
    )
    if name_seq is None or rel_seq is None:
        raise SapTableSchemaError(f"Unexpected FrameObj.GetHingeAssigns result: {result!r}")
    return [
        HingeAssign(frame=frame, hinge=str(hinge), rel_dist=float(rel_dist))
        for hinge, rel_dist in zip(name_seq, rel_seq, strict=True)
    ]
