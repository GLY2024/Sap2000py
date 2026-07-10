"""Fiber sections and moment-curvature analysis.

The computation core (constitutive models, fiber discretization, and the
moment-curvature solver) is pure NumPy and has **no COM dependency**, so it is
importable and testable on any platform. Building a fiber section directly from
complex geometry (via the ``sections`` module) additionally needs the
``sections`` extra.

Example
-------
>>> from sap2000py.fiber import (
...     BilinearSteel, ManderConcrete, FiberSection, moment_curvature,
... )
>>> sec = FiberSection()
>>> conc = ManderConcrete(fco=40.0, Ec=3.0e4)   # MPa, mm
>>> sec.add_rect_patch(conc, y_min=-300, y_max=300, width=500, n=40)
>>> steel = BilinearSteel(E=2.0e5, fy=400.0)
>>> sec.add_bars(steel, ys=[-250, 250], area_each=2000.0)
>>> mc = moment_curvature(sec, max_curvature=2e-5, axial=-1.0e6, n_steps=40)
"""

from __future__ import annotations

from .materials import (
    BilinearSteel,
    LinearElastic,
    ManderConcrete,
    UniaxialMaterial,
)
from .moment_curvature import (
    ConvergenceError,
    EquilibriumError,
    MomentCurvature,
    MomentCurvatureError,
    MomentCurvatureTermination,
    moment_curvature,
)
from .section import FiberSection

__all__ = [
    "BilinearSteel",
    "ConvergenceError",
    "EquilibriumError",
    "FiberSection",
    "LinearElastic",
    "ManderConcrete",
    "MomentCurvature",
    "MomentCurvatureError",
    "MomentCurvatureTermination",
    "UniaxialMaterial",
    "moment_curvature",
]
