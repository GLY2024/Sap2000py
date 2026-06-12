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


def test_call_tuple_nonzero_status_raises() -> None:
    with pytest.raises(SapApiError):
        gateway().call(lambda: ("x", 7), api_name="Add")


def test_value_returns_bare_scalar_without_status_check() -> None:
    # Count() returns 5 directly; must NOT be read as a failure status.
    assert gateway().value(lambda: 5, api_name="Count") == 5


def test_value_tuple_unpacks_and_checks() -> None:
    assert gateway().value(lambda: (42, 0), api_name="GetThing") == 42


def test_auto_bare_returns_as_is() -> None:
    assert gateway().auto(lambda: 6, api_name="GetPresentUnits") == 6


def test_auto_tuple_checks_status() -> None:
    with pytest.raises(SapApiError):
        gateway().auto(lambda: ("n", 1), api_name="Proxy")


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
