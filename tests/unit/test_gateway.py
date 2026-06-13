"""Tests for the ComGateway unpacking and error-handling rules."""

from __future__ import annotations

import pytest

from sap2000py.errors import SapApiError
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
