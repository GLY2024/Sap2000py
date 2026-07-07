"""Bridge seismic isolators modelled as nonlinear link elements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...model.link_props import FrictionDof, WenDof
from ..component import BridgeComponent

if TYPE_CHECKING:
    from ...model import Model


class LeadRubberBearing(BridgeComponent):
    """Lead-rubber bearing as a plastic-Wen link."""

    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        z: float,
        *,
        vertical_stiffness: float,
        shear_stiffness: float,
        yield_force: float,
        post_yield_ratio: float = 0.1,
        height: float = 0.0,
    ) -> None:
        super().__init__(name)
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.vertical_stiffness = float(vertical_stiffness)
        self.shear_stiffness = float(shear_stiffness)
        self.yield_force = float(yield_force)
        self.post_yield_ratio = float(post_yield_ratio)
        self.height = float(height)

    def _build(self, model: Model) -> None:
        bottom = model.points.add(self.x, self.y, self.z, name=f"{self.name}_b", merge=False)
        top = model.points.add(
            self.x, self.y, self.z + self.height, name=f"{self.name}_t", merge=False
        )
        wen = WenDof(self.shear_stiffness, self.yield_force, self.post_yield_ratio)
        prop = model.link_props.add_plastic_wen(
            f"{self.name}_prop",
            [self.vertical_stiffness, self.shear_stiffness, self.shear_stiffness, 0.0, 0.0, 0.0],
            nonlinear={"U2": wen, "U3": wen},
            dof=("U1", "U2", "U3"),
        )
        model.links.add_by_points(bottom, top, prop, name=self.name)
        self._set_anchor("bottom", bottom)
        self._set_anchor("top", top)


class FrictionPendulumBearing(BridgeComponent):
    """Friction-pendulum bearing as a friction-isolator link."""

    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        z: float,
        *,
        vertical_stiffness: float,
        initial_stiffness: float,
        friction_slow: float,
        friction_fast: float,
        rate: float,
        radius: float,
        height: float = 0.0,
    ) -> None:
        super().__init__(name)
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.vertical_stiffness = float(vertical_stiffness)
        self.initial_stiffness = float(initial_stiffness)
        self.friction_slow = float(friction_slow)
        self.friction_fast = float(friction_fast)
        self.rate = float(rate)
        self.radius = float(radius)
        self.height = float(height)

    def _build(self, model: Model) -> None:
        bottom = model.points.add(self.x, self.y, self.z, name=f"{self.name}_b", merge=False)
        top = model.points.add(
            self.x, self.y, self.z + self.height, name=f"{self.name}_t", merge=False
        )
        friction = FrictionDof(
            self.initial_stiffness,
            self.friction_slow,
            self.friction_fast,
            self.rate,
            self.radius,
        )
        prop = model.link_props.add_friction_isolator(
            f"{self.name}_prop",
            [
                self.vertical_stiffness,
                self.initial_stiffness,
                self.initial_stiffness,
                0.0,
                0.0,
                0.0,
            ],
            nonlinear={"U2": friction, "U3": friction},
            dof=("U1", "U2", "U3"),
        )
        model.links.add_by_points(bottom, top, prop, name=self.name)
        self._set_anchor("bottom", bottom)
        self._set_anchor("top", top)
