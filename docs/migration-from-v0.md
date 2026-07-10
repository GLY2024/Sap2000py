# Migrating from v0.1.x

`1.0` is a ground-up rewrite. The old `Saproject()` singleton and its
attribute tree are gone, replaced by an explicit `SapClient` and a typed
`model` facade. This page maps the old API to the new one.

If you are not ready to migrate, pin the old release or use the frozen tag:

```bash
pip install "sap2000py==0.1.3"
# or, during migration, reference the frozen snapshot:
pip install "git+https://github.com/GLY2024/Sap2000py@v0.1.3-legacy"
```

## The big change: no more singleton

The old code activated COM at import time and exposed a process-wide singleton:

```python
# v0.1.x
from Sap2000py import Saproject

Sap = Saproject()      # attached to / launched SAP2000 as a side effect
Sap.openSap()
Sap.File.New_Blank()
```

`1.0` makes the connection explicit and scoped:

```python
# v1.0
from sap2000py import SapClient, Units

with SapClient.launch(visible=True) as client:
    model = client.model
    model.files.new_blank(units=Units.KN_M_C)
```

Use `SapClient.attach()` to connect to an already-running instance (it raises
instead of silently launching a new one), or `SapClient.attach_or_launch()` for
the old fallback behavior, made explicit.

## Attribute / method mapping

| v0.1.x | v1.0 |
| --- | --- |
| `Saproject()` (import-time singleton) | `SapClient.launch(...)` / `SapClient.attach()` |
| `Sap.openSap()` | handled by `SapClient.launch(...)` |
| `Sap.closeSap()` | `client.close()` (or leave the `with` block) |
| `Sap._Model` | `client.raw_model` |
| `Sap._Object` | `client.raw_object` |
| `Sap.File.New_Blank()` | `client.model.files.new_blank(units=...)` |
| `Sap.File.Open(path)` | `client.model.files.open(path)` |
| `Sap.File.Save(path)` | `client.model.files.save(path)` |
| `Sap.setUnits("KN_m_C")` | `client.model.set_units(Units.KN_M_C)` |
| `Sap.Units` | `client.model.current_units` |
| (manual switch + switch back) | `with client.model.units(Units.KN_MM_C): ...` |
| `Sap.lockModel()` / `unlockModel()` | `client.model.set_locked(True / False)` |
| `Sap.is_locked` | `client.model.is_locked` |
| `Sap.SapVersion` | `client.version` |
| `Sap.Assign.PointObj.AddCartesian(...)` | `client.model.points.add(x, y, z)` |
| `Sap.Assign.PointObj.Set.Restraint(...)` | `client.model.points.ref(p).fix()` |
| any unwrapped OAPI call | `client.api.<Object>.<Method>(...)` |

## Strings vs handles

Creating an object now returns a live handle that stringifies to its name. It
stores the object name and owner model, not cached SAP2000 state:

```python
p1 = model.points.add(0, 0, 0)     # PointHandle
p1.fix()
model.points.ref("P1").fix()       # bind a raw name to this model
```

## Errors instead of silent failures

The old code often logged an OAPI error and continued. `1.0` raises
`SapApiError` on every non-zero return code. Catch that exception around an
operation only when its failure is expected and recoverable.

## Anything not yet wrapped

The typed `model` facade covers the high-frequency API. Everything else is
reachable through the dynamic proxy, with the same return-code checking:

```python
# old: Sap.Assign.FrameObj.Set.SomethingObscure(...)
client.api.FrameObj.SomethingObscure(...)
```

If even that is not enough, `client.raw_model` is the unwrapped comtypes object.
