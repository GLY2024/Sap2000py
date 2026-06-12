"""Unit tests for the P-M interaction envelope (pure NumPy)."""

from __future__ import annotations

import numpy as np
import pytest

from sap2000py.fiber import BilinearSteel, FiberSection, ManderConcrete
from sap2000py.yield_surface import pm_interaction


def _rc_section() -> FiberSection:
    sec = FiberSection()
    conc = ManderConcrete(fco=40.0, Ec=3.0e4, eps_cu=0.004)
    sec.add_rect_patch(conc, y_min=-300, y_max=300, width=500, n=60)
    steel = BilinearSteel(E=2.0e5, fy=400.0)
    sec.add_bars(steel, ys=[-250, 250], area_each=1500.0)
    return sec


def test_envelope_shapes() -> None:
    env = pm_interaction(_rc_section(), eps_cu=0.004, n_points=30)
    assert len(env.axial) == 30
    assert len(env.moment) == 30


def test_pure_compression_has_near_zero_moment() -> None:
    env = pm_interaction(_rc_section(), eps_cu=0.004, n_points=30)
    # First point is uniform compression: large negative axial, ~zero moment.
    assert env.axial[0] < 0
    assert abs(env.moment[0]) < 1e-3 * abs(env.max_moment)


def test_squash_load_magnitude_is_reasonable() -> None:
    # Uniform crush strain: |P| ~ concrete area * peak stress (order check).
    env = pm_interaction(_rc_section(), eps_cu=0.004, n_points=20)
    # Concrete 500x600 = 3e5 mm^2; at ~40 MPa that's ~1.2e7 N compression.
    assert -1.6e7 < env.squash_load < -6.0e6


def test_balanced_point_has_max_moment() -> None:
    env = pm_interaction(_rc_section(), eps_cu=0.004, n_points=40)
    # The peak moment occurs at an intermediate (balanced) axial, not the ends.
    idx = int(np.argmax(env.moment))
    assert 0 < idx < len(env.moment) - 1


def test_empty_section_raises() -> None:
    with pytest.raises(ValueError, match="no fibers"):
        pm_interaction(FiberSection(), eps_cu=0.004)
