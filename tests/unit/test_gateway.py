"""Tests for the ComGateway unpacking and error-handling rules."""

from __future__ import annotations

import pytest

import sap2000py.gateway as gateway_module
from sap2000py.errors import (
    MissingDependencyError,
    SapApiError,
    SapComError,
    SapNameNotFoundError,
)
from sap2000py.gateway import ComGateway, ErrorPolicy


def gateway() -> ComGateway:
    return ComGateway(sap_model=object())


def test_call_bare_zero_status_returns_none() -> None:
    assert gateway().call(lambda: 0, api_name="X") is None


def test_call_bare_nonzero_status_raises() -> None:
    with pytest.raises(SapApiError) as info:
        gateway().call(lambda: 1, api_name="Setter")
    assert info.value.code == 1
    assert info.value.api_name == "Setter"


def test_call_wraps_com_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeComError(Exception):
        def __init__(self, hresult: int) -> None:
            self.hresult = hresult
            super().__init__()

    def fail(*args: object) -> int:
        raise FakeComError(0x80004005)

    monkeypatch.setattr(gateway_module, "COMError", FakeComError)

    with pytest.raises(SapComError) as info:
        gateway().call(fail, "P1", 6, api_name="PointObj.SetRestraint")

    assert info.value.api_name == "PointObj.SetRestraint"
    assert info.value.args_passed == ("P1", 6)
    assert info.value.hresult == 0x80004005


def test_call_tuple_unpacks_single_out_and_checks_status() -> None:
    # (out, status) -> returns out, status checked
    assert gateway().call(lambda: ("P1", 0), api_name="Add") == "P1"


def test_call_tuple_multi_out_returns_tuple() -> None:
    assert gateway().call(lambda: (1.0, 2.0, 3.0, 0), api_name="Coord") == (1.0, 2.0, 3.0)


def test_call_list_return_is_handled_like_tuple() -> None:
    # comtypes returns a LIST for methods with [in, out] params (AddCartesian).
    assert gateway().call(lambda: ["1", 0], api_name="AddCartesian") == "1"


def test_call_list_multi_out() -> None:
    assert gateway().call(lambda: [1.0, 2.0, 3.0, 0], api_name="Coord") == (1.0, 2.0, 3.0)


def test_call_list_nonzero_status_raises() -> None:
    with pytest.raises(SapApiError):
        gateway().call(lambda: ["1", 1], api_name="AddCartesian")


def test_call_tuple_nonzero_status_raises() -> None:
    with pytest.raises(SapApiError):
        gateway().call(lambda: ("x", 7), api_name="Add")


def test_value_returns_bare_scalar_without_status_check() -> None:
    # Count() returns 5 directly; must NOT be read as a failure status.
    assert gateway().value(lambda: 5, api_name="Count") == 5


def test_value_tuple_unpacks_and_checks() -> None:
    assert gateway().value(lambda: (42, 0), api_name="GetThing") == 42


def test_auto_value_getter_bare_returns_value() -> None:
    # A leaf name in the value-getter set: the bare int is data, not a status.
    assert gateway().auto(lambda: 6, api_name="GetPresentUnits") == 6
    assert gateway().auto(lambda: 5, api_name="PointObj.Count") == 5
    # Even a zero from a value-getter is the value, returned unchecked.
    assert gateway().auto(lambda: 0, api_name="PointObj.Count") == 0


def test_auto_tuple_checks_status() -> None:
    with pytest.raises(SapApiError):
        gateway().auto(lambda: ("n", 1), api_name="Proxy")


def test_auto_bare_int_nonzero_status_raises() -> None:
    # The no-ship fix: a failed status-only mutation must not be silently dropped.
    with pytest.raises(SapApiError) as info:
        gateway().auto(lambda: 1, api_name="File.Save")
    assert info.value.code == 1
    assert "raw_model" in str(info.value)  # self-diagnosing hint


def test_auto_bare_int_zero_status_returns_zero_not_none() -> None:
    # Returning the int (not None) keeps ported `if ret != 0` guards valid.
    assert gateway().auto(lambda: 0, api_name="File.Save") == 0


def test_auto_bare_bool_passes_through() -> None:
    # bool is checked before int: GetResultsAvailable()==True is not "status 1".
    assert gateway().auto(lambda: True, api_name="DesignSteel.GetResultsAvailable") is True
    assert gateway().auto(lambda: False, api_name="GetModelIsLocked") is False


def test_auto_bare_str_and_float_pass_through() -> None:
    assert gateway().auto(lambda: "Global", api_name="GetPresentCoordSystem") == "Global"
    assert gateway().auto(lambda: 1.25, api_name="GetOAPIVersionNumber") == 1.25


def test_auto_warn_policy_returns_status_int() -> None:
    gw = ComGateway(sap_model=object(), policy=ErrorPolicy.WARN)
    # Under WARN the non-zero status is logged, not raised, and still returned.
    assert gw.auto(lambda: 2, api_name="File.Save") == 2


def test_warn_policy_does_not_raise() -> None:
    gw = ComGateway(sap_model=object(), policy=ErrorPolicy.WARN)
    assert gw.call(lambda: 1, api_name="Setter") is None  # logged, not raised


def test_args_are_forwarded() -> None:
    seen: list[tuple[int, int]] = []

    def fn(a: int, b: int) -> int:
        seen.append((a, b))
        return 0

    gateway().call(fn, 3, 4, api_name="Fn")
    assert seen == [(3, 4)]


def test_sap_com_error_message_formats_hresult_conditionally() -> None:
    with_hresult = SapComError("File.Save", ("model.sdb",), hresult=0x80004005)
    without_hresult = SapComError("File.Save", ("model.sdb",), hresult=None)

    assert str(with_hresult) == "COM call to 'File.Save' failed (HRESULT=0x80004005)."
    assert str(without_hresult) == "COM call to 'File.Save' failed."
    assert "HRESULT" not in str(without_hresult)


def test_missing_dependency_error_records_feature_extra_and_install_hint() -> None:
    error = MissingDependencyError("bridge YAML configs", "bridge")

    assert error.feature == "bridge YAML configs"
    assert error.extra == "bridge"
    assert str(error) == (
        "bridge YAML configs requires the optional 'bridge' dependencies. "
        "Install them with: pip install 'sap2000py[bridge]'"
    )


def test_name_not_found_error_without_available_names_omits_available_section() -> None:
    error = SapNameNotFoundError("PX", kind="point")

    assert str(error) == "No point named 'PX'."
    assert "Available names" not in str(error)


def test_name_not_found_error_at_available_name_limit_is_not_truncated() -> None:
    names = [f"P{i}" for i in range(25)]
    error = SapNameNotFoundError("PX", kind="point", available=names)

    assert str(error) == f"No point named 'PX'. Available names: {names!r}."
    assert "... and" not in str(error)


def test_sap_api_error_message_formats_hint_conditionally() -> None:
    without_hint = SapApiError("File.Save", ("model.sdb",), 7)
    with_hint = SapApiError("File.Save", ("model.sdb",), 7, hint="Use client.raw_model.")

    assert str(without_hint) == (
        "OAPI call 'File.Save' returned non-zero status 7. "
        "Arguments: ('model.sdb',)"
    )
    assert str(with_hint) == (
        "OAPI call 'File.Save' returned non-zero status 7. "
        "Arguments: ('model.sdb',)\n"
        "Use client.raw_model."
    )
