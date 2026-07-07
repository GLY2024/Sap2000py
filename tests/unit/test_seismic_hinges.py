"""Pure numeric tests for seismic hinge helpers."""

from __future__ import annotations

import pytest

from sap2000py.seismic.hinges import DamageStates, damage_states_from_mc, hinge_from_mc


class SyntheticMomentCurvature:
    """Minimal bilinearize() carrier for deterministic tests."""

    def bilinearize(self) -> tuple[float, float, float, float]:
        return 0.01, 100.0, 0.04, 120.0


class LowUltimateMomentCurvature:
    """Synthetic MC with mu_u below the default extensive threshold."""

    def bilinearize(self) -> tuple[float, float, float, float]:
        return 0.01, 100.0, 0.035, 115.0


def test_hinge_from_mc_uses_plastic_rotation_identity() -> None:
    mc = SyntheticMomentCurvature()

    hinge = hinge_from_mc(mc, name="H", hinge_length=2.5, residual=0.25)

    theta_u = (0.04 - 0.01) * 2.5
    assert hinge.name == "H"
    assert hinge.yield_moment == 100.0
    assert hinge.backbone[1] == (theta_u, 1.2)
    assert hinge.backbone[2] == (theta_u, 0.25)


def test_damage_states_from_mc_maps_none_to_ultimate_ductility() -> None:
    mc = SyntheticMomentCurvature()

    states = damage_states_from_mc(
        mc,
        mu=(1.0, 2.0, None),
        names=("slight", "moderate", "complete"),
    )

    assert states.quantity == "curvature_ductility"
    assert list(states.thresholds) == ["slight", "moderate", "complete"]
    assert states.thresholds == {"slight": 1.0, "moderate": 2.0, "complete": 4.0}


def test_damage_states_from_mc_rejects_nonascending_mu_u_substitution() -> None:
    with pytest.raises(ValueError, match=r"mu_u=3\.5"):
        damage_states_from_mc(LowUltimateMomentCurvature())


def test_damage_states_constructor_rejects_nonascending_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        DamageStates("curvature_ductility", {"slight": 1.0, "complete": 0.9})
