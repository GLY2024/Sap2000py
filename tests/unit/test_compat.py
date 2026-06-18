"""Tests for deterministic SAP2000 version compatibility tables."""

from __future__ import annotations

import pytest

from sap2000py.errors import SapCompatibilityError
from sap2000py.model._compat import frame_output_stations_args


def test_frame_output_stations_args_for_current_signature() -> None:
    assert frame_output_stations_args(
        25,
        my_type=2,
        max_seg=0.0,
        min_sec=5,
        no_ends=False,
        no_ptloads=False,
        item_type=0,
    ) == (2, 0.0, 5, False, False, 0)


def test_frame_output_stations_args_for_legacy_signature() -> None:
    assert frame_output_stations_args(
        24,
        my_type=2,
        max_seg=0.0,
        min_sec=5,
        no_ends=False,
        no_ptloads=False,
        item_type=0,
    ) == (2, 0.0, 5, False, False)


def test_frame_output_stations_unknown_version_raises_compatibility_error() -> None:
    with pytest.raises(SapCompatibilityError, match=r"FrameObj\.SetOutputStations"):
        frame_output_stations_args(
            99,
            my_type=2,
            max_seg=0.0,
            min_sec=5,
            no_ends=False,
            no_ptloads=False,
            item_type=0,
        )
