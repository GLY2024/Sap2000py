# Bridge components

The `sap2000py.bridge` package turns the repetitive parts of bridge modelling —
laying out piers, stacking bearings, threading a girder, tying it all together —
into a small set of composable, testable objects. It is the M4 layer of the
rewrite, and it deliberately fixes the two structural problems of the old bridge
code: 72 hidden `Saproject()` singleton calls, and engineering parameters
hard-coded inline.

The components themselves are pure Python and need no extra; YAML configs and
the shipped bearing preset helpers (`bearing_preset()` / `bearing_presets()`)
require the `bridge` extra (`pip install 'sap2000py[bridge]'`).

## The component model

Every piece is a [`BridgeComponent`](../reference/bridge.md#component-protocol).
A component is **pure data until you build it** — constructing one touches no
COM:

```python
from sap2000py.bridge import Pier

pier = Pier("P1", base=(40, 0, 0), height=12.0, section="Pier", segments=4)
```

Calling `build(model)` is what creates objects, and the model is passed in
**explicitly** (the break from the old global singleton — this is what makes
components unit-testable and reusable):

```python
pier.build(model)          # creates 5 joints + 4 frame elements
pier.anchor("top")         # -> the PointHandle other components connect to
```

After `build`, a component exposes named **anchors** — the joints it offers for
connection. A `Pier` has `bottom` and `top`; a `Bearing` has `bottom` and `top`;
a `Girder` has `n0, n1, …` plus `start`/`end`.

## Auto-connection

[`snap_connect`](../reference/bridge.md#auto-connection) joins two (usually
coincident) anchors so you never hand-write constraint or link boilerplate at
each interface:

```python
from sap2000py.bridge import snap_connect, Connection

snap_connect(model, pier.anchor("top"), bearing.anchor("bottom"),
             how=Connection.BODY)
```

Three strategies are available:

| `how` | What it creates | Use when |
| --- | --- | --- |
| `Connection.BODY` | A rigid-body joint constraint | The joints move as one rigid body (cap↔pier, pier↔bearing). |
| `Connection.EQUAL` | An equal-DOF joint constraint | Selected DOF are made equal without full rigid kinematics. |
| `Connection.RIGID_LINK` | A stiff two-joint link element | A constraint is unsuitable and you want an actual element. |

!!! tip "Merging vs. connecting"
    To truly *merge* two coincident joints into one, create the second point
    with `model.points.add(..., merge=True)` — merging happens at point
    creation. `snap_connect` is for keeping joints distinct but tied (e.g. the
    two ends of a zero-length bearing link).

## The components

| Component | Builds | Anchors |
| --- | --- | --- |
| [`Foundation`](../reference/bridge.md#components) | A base joint with a fixed restraint or a 6-DOF spring | `top` |
| [`Pier`](../reference/bridge.md#components) | A column from base to top, split into segments | `bottom`, `top` |
| [`Bearing`](../reference/bridge.md#components) | Two joints + a linear link property + the link | `bottom`, `top` |
| [`Girder`](../reference/bridge.md#components) | A line of frame elements through deck nodes | `n0…`, `start`, `end` |

```python
from sap2000py.bridge import Foundation, Bearing

Foundation("F1", 0, 0, 0, kind="fixed").build(model)
Foundation("F2", 0, 0, 0, kind="spring", stiffness=[1e6]*3 + [1e7]*3).build(model)

Bearing("B1", x=40, y=0, z=12, stiffness=[2e5, 2e5, 2e9, 0, 0, 0]).build(model)
```

## Assembling a whole bridge

[`ContinuousGirderBridge`](../reference/bridge.md#system-assemblers) lays supports
out at the cumulative span stations, builds a foundation → pier → bearing stack
at each, threads one girder across the bearing tops, and rigidly connects every
interface with `snap_connect`. Define the frame sections first, then build:

```python
from sap2000py import SapClient, Units
from sap2000py.bridge import ContinuousGirderBridge, bearing_preset

with SapClient.launch(visible=False) as client:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)
    m.materials.add_isotropic("C40", modulus=3.25e7, poisson=0.2, weight_per_volume=26.0)
    m.frame_sections.add_rectangle("Girder", material="C40", depth=2.0, width=6.0)
    m.frame_sections.add_rectangle("Pier", material="C40", depth=2.0, width=2.0)

    bridge = ContinuousGirderBridge(
        "B1",
        spans=[40, 40, 40],
        pier_height=12.0,
        girder_section="Girder",
        pier_section="Pier",
        bearing_stiffness=bearing_preset("pot_fixed"),
        pier_segments=4,
    )
    result = bridge.build(m)        # builds + connects everything
    print(len(result.piers), "supports,", len(result.connections), "connections")

    m.loads.cases.add_modal_eigen("MODAL", num_modes=12)
    m.files.save("bridge.sdb")
    m.analysis.run(cases=["MODAL"])
    print(m.results.modal_periods().to_pandas())
```

`build` returns a [`BridgeBuild`](../reference/bridge.md#system-assemblers) so you
can reach back into any component (e.g. `result.bearings[1].anchor("top")`) to
add loads or query results.

## Externalized parameters

Engineering parameters live in YAML, not in code. A whole bridge spec can be
loaded from a file (needs the `bridge` extra):

```yaml
# three_span.yaml
spans: [40, 40, 40]
pier_height: 12.0
girder_section: Girder
pier_section: Pier
bearing_stiffness: [1.0e9, 1.0e9, 2.0e10, 0.0, 0.0, 0.0]
foundation: fixed
```

```python
bridge = ContinuousGirderBridge.from_yaml("three_span.yaml")  # name = file stem
bridge.build(m)
```

Common bearing stiffnesses ship as named presets (see
[`bearing_preset`](../reference/bridge.md#presets)):

```python
from sap2000py.bridge import bearing_preset, bearing_presets

bearing_presets()                  # ['elastomeric_pad', 'pot_fixed', ...]
bearing_preset("elastomeric_pad")  # [2.0e5, 2.0e5, 2.0e9, 0.0, 0.0, 0.0]
```

## Extending it

Write your own component by subclassing `BridgeComponent` and implementing
`_build`, registering anchors with `_set_anchor`:

```python
from sap2000py.bridge import BridgeComponent

class Crossbeam(BridgeComponent):
    def __init__(self, name, left, right, section):
        super().__init__(name)
        self.left, self.right, self.section = left, right, section

    def _build(self, model):
        a = model.points.add(*self.left, merge=False)
        b = model.points.add(*self.right, merge=False)
        model.frames.add_by_points(a, b, section=self.section)
        self._set_anchor("left", a)
        self._set_anchor("right", b)
```

It now composes with `snap_connect` and the assemblers like any built-in
component.
