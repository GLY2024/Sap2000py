# Static checking & IDE completion

`sap2000py` is fully typed and ships a [PEP 561](https://peps.python.org/pep-0561/)
`py.typed` marker. That means type checkers (mypy, Pyright/Pylance) and editors
analyse **your** code against the library's types — you get autocomplete,
parameter hints, and red squiggles on misuse, with no stub package to install.

## Enums: discover the valid choices

Values that used to be magic numbers or free strings are enums, so the editor
offers the valid options and the type checker rejects the rest. Selecting a unit
system, for instance, completes from [`Units`](../reference/enums.md):

```python
from sap2000py import Units

m.files.new_blank(units=Units.KN_M_C)   # editor lists KN_M_C, N_MM_C, KIP_IN_F, …
m.files.new_blank(units="kN-m")         # type error: str is not Units
```

The same holds for [`ItemType`](../reference/enums.md),
[`MatType`](../reference/enums.md), [`LoadPatternType`](../reference/enums.md),
and the bridge [`Connection`](../reference/bridge.md#auto-connection) strategy.
Restraint masks are built with the [`DOF`](../reference/enums.md) helpers
(`DOF.fixed()`, `DOF.of("U1", "R3")`), so you never pass a mis-sized list.

## Typed model methods

Every method on the `model` facade is annotated, so completion and checking work
through the whole call chain:

```python
sec = m.frame_sections.add_rectangle("Pier", material=c40, depth=2.0, width=1.0)
m.frames.add_by_points(p1, p2, section=sec)   # FrameSectionHandle accepted
m.frames.add_by_points(p1, p2, section=42)    # type error: int is not a section
```

Object references are typed [handles](../reference/handles.md)
(`PointHandle`, `FrameHandle`, …). Public APIs accept the right handle type or a
raw name string. A handle from the same model is used as-is; a raw string is
bound through that manager with `ref()`. Passing the wrong handle noun or a
handle owned by another model raises immediately instead of silently routing a
call to the wrong SAP2000 instance.

## The native escape hatch

`client.api` is a dynamic proxy over the *entire* OAPI (see the
[native API guide](native-api.md)). Because it resolves everything at runtime, a
generated stub provides completion for it: `client.api.PointObj.AddCartesian(…)`
autocompletes the sub-objects and method names. The stub ships as
`sap2000py/native.pyi`.

The stub is intentionally permissive (`*args: Any -> Any`) — it exists for
discoverability, not argument-level checking. For a type-checked path, prefer the
`model` facade; reach for `client.api` when you need an OAPI method the facade
doesn't wrap yet.

Regenerate the stub after a SAP2000 upgrade (it reflects over the live API):

```bash
uv run python -m sap2000py._stubgen.gen_native_stubs
```

That command also audits the gateway's value-getter set against the live API and
warns if a SAP2000 version added a bare-value method (e.g. a new `Count*`) that
the proxy would otherwise misread as a status code.

## Checking your own project

Point your type checker at your code as usual — no special configuration is
needed:

```bash
mypy your_script.py
pyright your_script.py
```

If you vendor or stub SAP2000 itself, note that `comtypes` is Windows-only;
`sap2000py`'s pure-computation modules (`fiber`, `sections`, `bridge`) import and
type-check on any platform.
