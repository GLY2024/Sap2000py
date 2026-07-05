"""Deterministic SAP2000 version compatibility tables."""

from __future__ import annotations

from ..errors import SapCompatibilityError

_FRAME_OUTPUT_STATIONS_ARITY: dict[int, int] = {
    # Verified against SAP2000 25 CSI_OAPI_Documentation.chm / SAP2000v1.tlb.
    25: 6,
}


def frame_output_stations_args(
    major: int,
    *,
    my_type: int,
    max_seg: float,
    min_sec: int,
    no_ends: bool,
    no_ptloads: bool,
    item_type: int,
) -> tuple[object, ...]:
    """Return version-specific args after the frame name for SetOutputStations."""
    arity = _FRAME_OUTPUT_STATIONS_ARITY.get(major)
    if arity is None:
        raise SapCompatibilityError(
            "No compatibility entry for FrameObj.SetOutputStations "
            f"on SAP2000 major version {major}."
        )
    args: tuple[object, ...] = (my_type, max_seg, min_sec, no_ends, no_ptloads, item_type)
    return args
