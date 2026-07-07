# Plastic hinges and seismic isolators

## MC to Moment-M3 hinges

`sap2000py.seismic.hinges.hinge_from_mc()` converts a
`fiber.MomentCurvature` result into a `MomentHinge` with yield moment,
plastic-rotation backbone points, and acceptance criteria:

```python
from sap2000py.seismic.hinges import hinge_from_mc

hinge = hinge_from_mc(mc, name="PierP1_M3", hinge_length=0.8)
print(hinge.yield_moment)
print(hinge.backbone)
print(hinge.acceptance)
```

The MC to `MomentHinge` computation is fully functional. Pushing that hinge
definition into SAP2000 through interactive database tables is not available on
SAP2000 v25 for a model with no pre-existing hinges. On a blank v25 model,
`GetAvailableTables` returns no hinge definition tables and no frame hinge
assignment tables, so table-based hinge creation cannot bootstrap itself.

`model.hinges.define_moment_m3()` and `model.hinges.assign()` therefore raise
`SapTableSchemaError` when the required hinge tables are absent. The exception
lists the tables discovered from the running SAP2000 model.

Recommended v25 workflow:

1. Use `hinge_from_mc()` to compute the `MomentHinge` values.
2. Define the hinge in SAP2000 from those values through
   **Define > Section Properties > Hinge Properties**, or create a Section
   Designer fiber hinge.
3. Assign the hinge in SAP2000.
4. Use `model.hinges.assigned()` and `model.hinges.states()` for
   read-back and verification; `FrameObj.GetHingeAssigns` is exposed by v25.

## Fiber hinge feasibility

`model.hinges.assign_auto_fiber(frame, rel_dist=..., hinge_length=...)`
attempts the native SAP2000 P-M2-M3 fiber-hinge table route. This is a
go/no-go spike. If the native fiber table or fields are absent, the method
raises `SapTableSchemaError` and instructs you to create/export one manual
fiber hinge assignment as a version-specific template.

## Isolator components

`LeadRubberBearing` and `FrictionPendulumBearing` are bridge components with
the same `bottom` and `top` anchors as `Bearing`. They create two points, a
nonlinear link property, and one link object.

YAML bridge specs can select a preset:

```yaml
bearing:
  type: lead_rubber
  preset: lrb_520
```

Omitting `bearing:` keeps the existing linear `Bearing` behavior.
