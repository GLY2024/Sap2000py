from __future__ import annotations

import numpy as np
import pytest

from sap2000py.enums import Units
from sap2000py.errors import GroundMotionParseError
from sap2000py.seismic.ground_motion import (
    GroundMotionRecord,
    GroundMotionSuite,
    gravity,
    read_record,
    read_suite,
)

FIXTURES = __file__.replace("test_ground_motion.py", "fixtures/gm")


def test_gravity_converts_to_length_unit() -> None:
    assert gravity(Units.KN_M_C) == pytest.approx(9.80665)
    assert gravity(Units.KN_MM_C) == pytest.approx(9806.65)
    assert gravity(Units.KIP_FT_F) == pytest.approx(32.1740485564)


def test_read_peer_at2_record() -> None:
    record = read_record(f"{FIXTURES}/peer_at2.at2")

    assert record.name == "peer_at2"
    assert record.dt == pytest.approx(0.02)
    assert record.npts == 5
    assert record.duration == pytest.approx(0.08)
    assert record.pga == pytest.approx(0.4)


def test_read_two_column_and_convert_cm_per_s2_to_g() -> None:
    record = read_record(f"{FIXTURES}/two_column_cm.txt")

    assert record.dt == pytest.approx(0.05)
    assert record.npts == 3
    assert record.pga == pytest.approx(0.2)


def test_read_single_column_with_dt_header() -> None:
    record = read_record(f"{FIXTURES}/single_header_g.txt")

    assert record.dt == pytest.approx(0.1)
    assert record.npts == 4
    assert record.pga == pytest.approx(0.2)


def test_read_wrapped_stream_and_convert_m_per_s2_to_g() -> None:
    record = read_record(f"{FIXTURES}/wrapped_mps2.txt")

    assert record.dt == pytest.approx(0.02)
    assert record.npts == 6
    assert record.pga == pytest.approx(0.2)


def test_read_csv_and_convert_gal_to_g() -> None:
    record = read_record(f"{FIXTURES}/csv_gal.csv", fmt="csv")

    assert record.dt == pytest.approx(0.1)
    assert record.npts == 3
    assert record.pga == pytest.approx(0.1)


def test_explicit_unit_wins_over_header(tmp_path) -> None:
    path = tmp_path / "explicit.txt"
    path.write_text("units: g\nDT=0.1\n0\n98.0665\n", encoding="utf-8")

    record = read_record(path, unit="cm/s2")

    assert record.pga == pytest.approx(0.1)


def test_bom_is_accepted(tmp_path) -> None:
    path = tmp_path / "bom.txt"
    path.write_text("\ufeffunits: g\nDT=0.1\n0\n0.2\n", encoding="utf-8")

    record = read_record(path)

    assert record.pga == pytest.approx(0.2)


def test_missing_units_raise_with_diagnostics(tmp_path) -> None:
    path = tmp_path / "missing_units.txt"
    path.write_text("DT=0.1\n0\n0.2\n", encoding="utf-8")

    with pytest.raises(GroundMotionParseError) as exc_info:
        read_record(path)

    assert "Attempts" in str(exc_info.value)
    assert hasattr(exc_info.value, "diagnostics")


def test_mixed_delimiters_raise(tmp_path) -> None:
    path = tmp_path / "mixed.txt"
    path.write_text("units: g\n0.0 0.0\n0.1,0.2\n", encoding="utf-8")

    with pytest.raises(GroundMotionParseError, match="mixed delimiters"):
        read_record(path)


def test_trailing_junk_raises(tmp_path) -> None:
    path = tmp_path / "junk.txt"
    path.write_text("units: g\nDT=0.1\n0\n0.2\nend\n", encoding="utf-8")

    with pytest.raises(GroundMotionParseError, match="trailing line"):
        read_record(path)


def test_suite_summary_and_scaling() -> None:
    first = GroundMotionRecord("r1", 0.1, np.asarray([0.0, 0.2], dtype=np.float64))
    second = GroundMotionRecord("r2", 0.2, np.asarray([0.0, -0.3], dtype=np.float64))
    suite = GroundMotionSuite((first, second))

    assert suite[0] is first
    assert suite["r2"] is second
    assert suite.scaled(2.0)["r1"].pga == pytest.approx(0.4)
    assert suite.summary()["name"] == ("r1", "r2")


def test_read_suite_reads_matching_files() -> None:
    suite = read_suite(FIXTURES, pattern="*.csv")

    assert len(suite) == 1
    assert suite[0].name == "csv_gal"
