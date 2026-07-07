"""Interactive database table access."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..errors import SapTableSchemaError
from ..handles import Handle
from ._base import Manager
from .results import ResultTable, _columns


@dataclass(frozen=True)
class TableApplyLog:
    """Summary returned by ``DatabaseTables.ApplyEditedTables``."""

    fatal: int
    errors: int
    warnings: int
    info: int
    log: str


class DatabaseTables(Manager[Handle]):
    """Read and edit SAP2000 interactive database tables."""

    def available(self, *, editable_only: bool = False) -> list[str]:
        """Return available table keys.

        Wraps ``DatabaseTables.GetAvailableTables``.
        """
        _count, keys, _names, import_types = self._g.call(
            self._raw.DatabaseTables.GetAvailableTables,
            api_name="DatabaseTables.GetAvailableTables",
        )
        if not keys:
            return []
        if not editable_only:
            return list(keys)
        return [
            str(key)
            for key, import_type in zip(keys, import_types or (), strict=False)
            if int(import_type) > 0
        ]

    def fields(self, table_key: str) -> ResultTable:
        """Return field metadata for ``table_key``.

        Wraps ``DatabaseTables.GetAllFieldsInTable``.
        """
        table_version, _count, field_keys, field_names, descriptions, units, importable = (
            self._g.call(
                self._raw.DatabaseTables.GetAllFieldsInTable,
                table_key,
                api_name="DatabaseTables.GetAllFieldsInTable",
            )
        )
        count = len(field_keys or ())
        return ResultTable(
            _columns(
                ["table_version", "field_key", "field_name", "description", "units", "importable"],
                [
                    [table_version] * count,
                    field_keys,
                    field_names,
                    descriptions,
                    units,
                    importable,
                ],
            )
        )

    def get(  # type: ignore[override]
        self,
        table_key: str,
        *,
        fields: Sequence[str] = ("All",),
        group: str = "All",
    ) -> ResultTable:
        """Return a display table.

        Wraps ``DatabaseTables.GetTableForDisplayArray``.
        """
        _version, included_fields, record_count, table_data = self._g.call(
            self._raw.DatabaseTables.GetTableForDisplayArray,
            table_key,
            list(fields),
            group,
            api_name="DatabaseTables.GetTableForDisplayArray",
        )
        field_names = [str(field) for field in included_fields or ()]
        values = list(table_data or ())
        width = len(field_names)
        if width == 0:
            return ResultTable({})
        expected = int(record_count) * width
        if len(values) != expected:
            raise SapTableSchemaError(
                f"Table {table_key!r} returned {len(values)} values for "
                f"{record_count} records x {width} fields."
            )
        columns = {
            field: tuple(values[index::width]) for index, field in enumerate(field_names)
        }
        return ResultTable(columns)

    def edit(self, table_key: str, columns: Mapping[str, Sequence[Any]]) -> None:
        """Stage table data for editing.

        Wraps ``DatabaseTables.SetTableForEditingArray``.
        """
        if not columns:
            raise ValueError("columns cannot be empty.")
        field_names = list(columns)
        lengths = {len(values) for values in columns.values()}
        if len(lengths) != 1:
            raise ValueError("all columns must have the same length.")
        record_count = lengths.pop()
        table_data = [
            columns[field][row]
            for row in range(record_count)
            for field in field_names
        ]
        self._g.call(
            self._raw.DatabaseTables.SetTableForEditingArray,
            table_key,
            0,
            field_names,
            record_count,
            table_data,
            api_name="DatabaseTables.SetTableForEditingArray",
        )

    def apply(self, *, raise_on_error: bool = True) -> TableApplyLog:
        """Apply staged table edits.

        Wraps ``DatabaseTables.ApplyEditedTables``.
        """
        fatal, errors, warnings, info, log = self._g.call(
            self._raw.DatabaseTables.ApplyEditedTables,
            True,
            api_name="DatabaseTables.ApplyEditedTables",
        )
        apply_log = TableApplyLog(
            fatal=int(fatal),
            errors=int(errors),
            warnings=int(warnings),
            info=int(info),
            log=str(log),
        )
        if raise_on_error and (apply_log.fatal or apply_log.errors):
            raise SapTableSchemaError(
                "Database table edits were rejected by SAP2000.",
                apply_log=apply_log,
            )
        return apply_log

    def names(self) -> list[str]:
        """Available table keys. Wraps ``DatabaseTables.GetAvailableTables``."""
        return self.available()
