# Fiber moment-curvature

The `sap2000py.fiber` package computes the moment-curvature response of a
cross-section under constant axial load. The computation core is pure NumPy
with **no COM dependency**, so it runs and is tested on any platform.

## Constitutive models

Tension-positive sign convention throughout.

- `ManderConcrete(fco, Ec=..., fcc=..., eps_co=..., eps_cu=...)` — Mander,
  Priestley & Park (1988); confined when `fcc > fco`. No tension capacity.
- `BilinearSteel(E, fy, hardening=0.01, eps_ult=...)` — elastic-plastic with
  linear strain hardening and optional rupture.
- `LinearElastic(E)` — for elastic checks.

## Build a section and solve

```python
from sap2000py.fiber import (
    FiberSection, ManderConcrete, BilinearSteel, moment_curvature,
)

# Consistent N, mm, MPa units.
sec = FiberSection()
sec.add_rect_patch(ManderConcrete(40.0, Ec=3.0e4), y_min=-300, y_max=300, width=500, n=60)
sec.add_bars(BilinearSteel(2.0e5, 400.0), ys=[-250, 250], area_each=1500.0)

mc = moment_curvature(sec, max_curvature=3e-5, axial=-2.0e6, n_steps=60)
phi_y, m_y, phi_u, m_u = mc.bilinearize()
```

## Interaction surface

```python
from sap2000py.yield_surface import pm_interaction

env = pm_interaction(sec, eps_cu=0.004)
print(env.squash_load, env.max_moment)
```
