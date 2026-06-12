"""End-to-end smoke test against a real SAP2000 install.

Run with ``pytest --sap``. This is the M1 verification: launch a headless
instance, build a trivial model, save it, and close — exercising the real
comtypes marshalling that unit tests (with a fake COM) cannot.
"""

from __future__ import annotations

import pytest

from sap2000py import DOF, SapClient, Units

pytestmark = pytest.mark.sap


@pytest.fixture(scope="module")
def client():
    c = SapClient.launch(visible=False, units=Units.KN_M_C)
    try:
        yield c
    finally:
        c.close()


def test_launch_reports_version(client: SapClient) -> None:
    assert client.version  # non-empty version string


def test_units_roundtrip(client: SapClient) -> None:
    client.model.files.new_blank(units=Units.KN_M_C)
    assert client.model.current_units == Units.KN_M_C
    with client.model.units(Units.KN_MM_C):
        assert client.model.current_units == Units.KN_MM_C
    assert client.model.current_units == Units.KN_M_C


def test_build_and_query_points(client: SapClient) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    p1 = m.points.add(0, 0, 0)
    p2 = m.points.add(0, 0, 10)
    assert m.points.count() == 2
    assert m.points.coordinates(p2)[2] == pytest.approx(10.0)
    m.points.set_restraints(p1, DOF.fixed())


def test_native_proxy_matches_typed_layer(client: SapClient) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    name = client.api.PointObj.AddCartesian(1.0, 1.0, 1.0, "", "", "Global", False, 0)
    assert isinstance(name, str)
    assert client.api.PointObj.Count() == 1


def test_save_creates_file(client: SapClient, tmp_path) -> None:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    m.points.add(0, 0, 0)
    target = tmp_path / "smoke.sdb"
    m.files.save(target)
    assert target.exists()
