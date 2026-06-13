# Building and analyzing models

`client.model` groups the everyday API into managers. This guide walks through a
full build → analyze → extract cycle. A complete runnable script is in
[`examples/portal_frame.py`](https://github.com/GLY2024/Sap2000py/blob/main/examples/portal_frame.py).

## Materials

```python
# Explicit isotropic material (units follow the model's current units).
m.materials.add_isotropic("STEEL", modulus=2.0e8, poisson=0.3, weight_per_volume=78.5)

# Chinese-code materials (the old Common_Material_Set, now first-class).
c40 = m.materials.add_concrete("C40", grade="C40", code="JTG")   # GB / JTG / TB
q345 = m.materials.add_steel("Q345", grade="Q345", code="GB")
```

For any other code grade, use `m.materials.add(name, MatType.CONCRETE, grade="...")`
with the exact SAP2000 grade string.

## Sections

```python
m.frame_sections.add_rectangle("COL", material="STEEL", depth=0.4, width=0.4)
m.frame_sections.add_circle("PILE", material="C40", diameter=1.2)
m.frame_sections.add_general("BOX", material="STEEL", depth=2.0, width=5.0,
                             area=0.86, as2=0.48, as3=0.08,
                             torsion=3.1, i22=2.3, i33=23.0)
```

## Geometry and restraints

```python
from sap2000py import DOF

base = m.points.add(0, 0, 0)
top = m.points.add(0, 0, 3)
m.points.set_restraints(base, DOF.fixed())      # or DOF.pinned(), DOF.of("U1", "U3")
col = m.frames.add_by_points(base, top, section="COL")
m.frames.set_releases(col, i_end=DOF.free(), j_end=DOF.of("R2", "R3"))
```

Creators return typed handles that stringify to their name, so handles and raw
names are interchangeable.

## Loads

A blank model already has a default `DEAD` pattern (self-weight 1.0) and case.

```python
from sap2000py import LoadPatternType

m.loads.patterns.set_self_weight("DEAD", 1.0)             # adjust the default
m.loads.patterns.add("WIND", pattern_type=LoadPatternType.WIND)

m.loads.cases.add_static_linear("SLS", loads={"DEAD": 1.0, "WIND": 0.6})
m.loads.cases.add_modal_eigen("MODAL", num_modes=12)
```

## Analyze

The model must be saved first — SAP2000 writes its analysis files next to the
`.sdb`. The library raises a clear error if you forget.

```python
m.files.save("model.sdb")
report = m.analysis.run(cases=["MODAL", "SLS"])   # None runs everything
assert report.all_finished
```

## Extract results

```python
m.results.select_output(cases=["SLS"])

periods = m.results.modal_periods()
reactions = m.results.joint_reactions(base)
forces = m.results.frame_forces(col)

print(periods.to_pandas())          # needs the `tables` extra
for row in reactions.rows():        # always available
    print(row["F3"])
```
