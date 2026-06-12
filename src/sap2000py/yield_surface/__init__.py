"""Axial-moment (P-M) yield/interaction surfaces built from fiber sections.

Pure NumPy, building on :mod:`sap2000py.fiber`; no COM dependency.

>>> from sap2000py.fiber import FiberSection, ManderConcrete, BilinearSteel
>>> from sap2000py.yield_surface import pm_interaction
>>> sec = FiberSection()
>>> sec.add_rect_patch(ManderConcrete(40.0, Ec=3.0e4), y_min=-300, y_max=300, width=500, n=40)
>>> sec.add_bars(BilinearSteel(2.0e5, 400.0), ys=[-250, 250], area_each=1500.0)
>>> env = pm_interaction(sec, eps_cu=0.004)
"""

from __future__ import annotations

from .surface import PMInteraction, pm_interaction

__all__ = ["PMInteraction", "pm_interaction"]
