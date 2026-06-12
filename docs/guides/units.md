# Units

SAP2000 has a single "present units" setting that affects how values you pass
in and read back are interpreted. The old code switched units imperatively and
relied on remembering to switch back — a common source of silent errors.

`1.0` makes units explicit and, crucially, gives you a **restoring context
manager** so a block can never leave the model in the wrong units.

## The `Units` enum

`Units` mirrors the OAPI `eUnits` ids exactly, so it is unambiguous:

```python
from sap2000py import Units

Units.KN_M_C      # kN, m, °C
Units.KN_MM_C     # kN, mm, °C
Units.N_M_C       # N, m, °C
```

## Read and set

```python
model.current_units            # -> Units
model.set_units(Units.KN_M_C)  # permanent switch
```

## Switch temporarily

Prefer the context manager whenever a calculation needs specific units. The
previous units are always restored, even if the block raises:

```python
with model.units(Units.KN_MM_C):
    model.frame_sections.add_general(...)   # defined in mm
# back to whatever units were active before
```

This is the recommended way to define section or material properties that are
naturally expressed in a particular unit system, without disturbing the rest of
your modelling code.
