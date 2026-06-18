# Quickstart

## Connect

```python
from sap2000py import SapClient, Units

# Launch a new instance and tear it down when the block exits.
with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
    model = client.model
    ...
```

Other ways to connect:

```python
client = SapClient.attach()             # an already-running instance (raises if none)
client = SapClient.attach_or_launch()   # attach, else launch
```

When you launch, you own the process — `close()` (or the `with` block) exits
SAP2000. When you `attach`, you don't — closing just drops the connection.

## Build a tiny model

```python
from sap2000py import SapClient, Units

with SapClient.launch(visible=False) as client:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)

    # A column from the ground up.
    mat = m.materials.add_concrete("C40", code="JTG")
    sec = m.frame_sections.add_rectangle("COL", material=mat, depth=0.4, width=0.4)

    base = m.points.add(0, 0, 0)
    top = m.points.add(0, 0, 10)
    base.fix()
    col = m.frames.add_by_points(base, top, section=sec)

    print("points:", m.points.count())
    print("frames:", m.frames.count())
    print("top z:", top.coordinates()[2])
    print("column length:", col.length)

    m.files.save(r"C:\tmp\column.sdb")
```

## Live handles

Object creators return a live handle: a typed reference to an object in SAP2000
by name. It stores no model state, and each method round-trips to SAP2000:

```python
p = m.points.add(1, 2, 3)     # PointHandle("P1")
p.pin()                       # fix() / pin() / free() for the common supports
m.points.ref("P1").pin()      # bind a raw name to this model
p.restrain("U1", "R3")        # or name exactly which DOF to restrain
```

For result extraction, single-object handle methods are immediate and read the
current output selection. Use `m.results.batch(...).collect()` when you want to
select cases once and read many objects, groups, or the current SAP2000
selection.

## Reach the rest of the OAPI

The typed `model` facade wraps the common API. Everything else is one attribute
chain away through the dynamic proxy — and it is still return-code checked:

```python
name = client.api.PointObj.AddCartesian(0, 0, 0, "", "", "Global", False, 0)
count = client.api.PointObj.Count()
```

See [the native API guide](guides/native-api.md) for the details and the
ultimate `client.raw_model` escape hatch.
