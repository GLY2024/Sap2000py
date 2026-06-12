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
from sap2000py import SapClient, Units, DOF

with SapClient.launch(visible=False) as client:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)

    # A column from the ground up.
    base = m.points.add(0, 0, 0)
    top = m.points.add(0, 0, 10)
    m.points.set_restraints(base, DOF.fixed())

    print("points:", m.points.count())
    print("top z:", m.points.coordinates(top)[2])

    m.files.save(r"C:\tmp\column.sdb")
```

## Handles or names

Object creators return a typed handle that stringifies to its name. Anywhere an
object is expected, a handle or a raw name string both work:

```python
p = m.points.add(1, 2, 3)     # PointHandle("P1")
m.points.set_restraints(p, DOF.pinned())
m.points.set_restraints("P1", DOF.pinned())   # equivalent
```

## Reach the rest of the OAPI

The typed `model` facade wraps the common API. Everything else is one attribute
chain away through the dynamic proxy — and it is still return-code checked:

```python
name = client.api.PointObj.AddCartesian(0, 0, 0, "", "", "Global", False, 0)
count = client.api.PointObj.Count()
```

See [the native API guide](guides/native-api.md) for the details and the
ultimate `client.raw_model` escape hatch.
