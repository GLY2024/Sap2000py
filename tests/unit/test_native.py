"""Tests for the dynamic NativeApi proxy."""

from __future__ import annotations

import pytest

from sap2000py.errors import SapApiError


def test_proxy_walks_tree_and_calls_method(make_proxy) -> None:
    api, calls = make_proxy({"PointObj.AddCartesian": ("P1", 0)})
    result = api.PointObj.AddCartesian(0.0, 0.0, 0.0, "", "", "Global", False, 0)
    assert result == "P1"
    assert calls == [("PointObj.AddCartesian", (0.0, 0.0, 0.0, "", "", "Global", False, 0))]


def test_proxy_bare_value_returned_as_is(make_proxy) -> None:
    api, _ = make_proxy({"PointObj.Count": 5})
    assert api.PointObj.Count() == 5


def test_proxy_list_return_unpacks_out_param(make_proxy) -> None:
    # comtypes hands [in, out] methods back as a list; the proxy must unpack it.
    api, _ = make_proxy({"PointObj.AddCartesian": ["1", 0]})
    assert api.PointObj.AddCartesian(0.0, 0.0, 0.0, "", "", "Global", False, 0) == "1"


def test_proxy_tuple_status_checked(make_proxy) -> None:
    api, _ = make_proxy({"FrameObj.SetSection": ("bad", 1)})
    with pytest.raises(SapApiError):
        api.FrameObj.SetSection("F1", "SEC")


def test_proxy_private_attr_raises_attributeerror(make_proxy) -> None:
    api, _ = make_proxy({})
    with pytest.raises(AttributeError):
        _ = api._not_a_real_thing


def test_proxy_api_name_is_dotted_path(make_proxy) -> None:
    api, _ = make_proxy({"FrameObj.SetSection": ("x", 1)})
    with pytest.raises(SapApiError) as info:
        api.FrameObj.SetSection("F1", "SEC")
    assert info.value.api_name == "FrameObj.SetSection"
