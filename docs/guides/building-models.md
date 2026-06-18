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

> **Creation methods follow one rule.** Each manager is a result noun; its
> `add_*` methods are the creation variants — `add_<subtype>` when the product
> differs (`add_concrete`, `add_rectangle`) and `add_by_<input>` when only the
> inputs differ (`add_by_points`, `add_by_coord`). A bare `add` appears when a
> noun has no variants (`points.add`, `groups.add`) or exposes a direct OAPI
> creator (`materials.add`). Type `m.materials.add_` and let autocomplete list
> every creator — the `add_` prefix is the discovery namespace.

## Geometry and restraints

```python
from sap2000py import DOF

base = m.points.add(0, 0, 0)
top = m.points.add(0, 0, 3)
base.fix()                                      # fixed support; pin() / free() too
# custom: base.restrain("U1", "U3") names exactly which DOF to restrain
col = m.frames.add_by_points(base, top, section="COL").release(j_end=DOF.of("R2", "R3"))
```

Creators return live handles that stringify to their name. They store only the
object name and owner model; methods such as `base.fix()`,
`top.coordinates()`, and `col.forces()` round-trip to SAP2000 each time.

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
reactions = base.reactions()
forces = col.forces()

print(periods.to_pandas())          # needs the `tables` extra
for row in reactions.rows():        # always available
    print(row["F3"])
```

For many objects, use the delayed batch API. It changes the SAP2000 output
selection only when `cases=` or `combos=` is provided, and it does so once at
`collect()` time:

```python
tables = (
    m.results.batch(cases=["SLS"])
    .frame_forces(group="PierFrames", key="pier_forces")
    .joint_reactions(group="Supports", key="support_reactions")
    .collect()
)

selected = m.results.batch().frame_forces(selection=True, key="selected").collect()
```

`selection=True` means the current SAP2000 object selection; it does not select
or deselect objects for you. For arbitrary lists, `frames=[...]` and
`points=[...]` default to object-by-object reads. `strategy="temporary_group"` is
an explicit opt-in when you want SAP2000's group result path for one batch.
