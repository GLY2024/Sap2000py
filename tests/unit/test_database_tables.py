"""Unit tests for the DatabaseTables manager."""

from __future__ import annotations

from typing import Any

import pytest

from sap2000py import SapTableSchemaError


def table_responses() -> dict[str, Any]:
    """Fake COM table surface."""
    return {
        "DatabaseTables.GetAvailableTables": (
            2,
            ("Editable", "Read Only"),
            ("Editable Table", "Read Only Table"),
            (1, 0),
            0,
        ),
        "DatabaseTables.GetAllFieldsInTable": (
            25,
            2,
            ("Name", "Value"),
            ("Name", "Value"),
            ("Object name", "Object value"),
            ("", "kN"),
            (True, True),
            0,
        ),
        "DatabaseTables.GetTableForDisplayArray": (
            25,
            ("Name", "Value"),
            2,
            ("A", "1.0", "B", "2.0"),
            0,
        ),
        "DatabaseTables.SetTableForEditingArray": 0,
        "DatabaseTables.ApplyEditedTables": (0, 0, 1, 2, "ok", 0),
    }


def test_database_tables_available_fields_get_and_edit(make_model) -> None:
    h = make_model(table_responses())

    assert h.model.database_tables.available() == ["Editable", "Read Only"]
    assert h.model.database_tables.available(editable_only=True) == ["Editable"]

    fields = h.model.database_tables.fields("Editable")
    table = h.model.database_tables.get("Editable", fields=("Name", "Value"), group="G")
    h.model.database_tables.edit("Editable", {"Name": ["A", "B"], "Value": [1.0, 2.0]})
    log = h.model.database_tables.apply()

    assert fields["field_key"] == ("Name", "Value")
    assert table.rows() == [{"Name": "A", "Value": "1.0"}, {"Name": "B", "Value": "2.0"}]
    assert h.called("DatabaseTables.GetTableForDisplayArray")[0] == (
        "Editable",
        ["Name", "Value"],
        "G",
    )
    assert h.called("DatabaseTables.SetTableForEditingArray")[0] == (
        "Editable",
        0,
        ["Name", "Value"],
        2,
        ["A", 1.0, "B", 2.0],
    )
    assert h.called("DatabaseTables.ApplyEditedTables")[0] == (True,)
    assert log.warnings == 1
    assert log.info == 2


def test_database_tables_apply_raises_on_errors(make_model) -> None:
    responses = table_responses()
    responses["DatabaseTables.ApplyEditedTables"] = (0, 2, 0, 0, "bad import", 0)
    h = make_model(responses)

    with pytest.raises(SapTableSchemaError) as excinfo:
        h.model.database_tables.apply()

    assert excinfo.value.apply_log.errors == 2
    assert excinfo.value.apply_log.log == "bad import"


def test_database_tables_get_rejects_bad_shape(make_model) -> None:
    responses = table_responses()
    responses["DatabaseTables.GetTableForDisplayArray"] = (25, ("A", "B"), 2, ("only",), 0)
    h = make_model(responses)

    with pytest.raises(SapTableSchemaError, match="returned 1 values"):
        h.model.database_tables.get("Bad")
