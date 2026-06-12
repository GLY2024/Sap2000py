# Architecture

Three layers sit between your code and SAP2000's COM API.

```
your code
   │
   ├── client.model  ──►  typed managers (files, points, frames, ...)
   │                          │
   ├── client.api    ──►  NativeApi (dynamic proxy over the whole OAPI)
   │                          │
   │                          ▼
   │                     ComGateway   ◄── the single chokepoint
   │                          │            (return-code check, unpack, raise)
   ▼                          ▼
SapClient ──────────────►  cSapModel (raw comtypes object)
```

## SapClient — connection lifecycle

`SapClient` owns one COM connection. You create it explicitly with
[`launch()`](reference/client.md) or [`attach()`](reference/client.md);
importing the package does nothing to SAP2000. `comtypes` is imported lazily
inside those methods, so the package — and the pure-Python computation modules
(`fiber`, `yield_surface`) — import fine on any platform.

A launched instance is owned by the client and is shut down by `close()` (or by
leaving the `with` block). An attached instance is left running.

## ComGateway — the single chokepoint

Every OAPI call goes through one place. The old code scattered raw calls across
~9,000 lines and checked the return code inconsistently. `ComGateway`:

1. invokes the COM method and wraps any `comtypes.COMError` as `SapComError`;
2. unpacks comtypes' by-ref out-parameters;
3. checks the OAPI status and raises `SapApiError` on a non-zero code.

The unpacking handles a real-machine subtlety: comtypes returns a **list** for
methods with `[in, out]` parameters and a **tuple** for pure `[out]` methods.
The gateway treats both identically — the last element is always the status.

## NativeApi — full OAPI coverage in ~30 lines

`client.api` is a dynamic proxy. Attribute access walks the COM object tree and
method calls route through the gateway, so the *entire* OAPI is reachable with
the same error handling without hand-writing a wrapper per method. This single
class replaces the old 5,465-line passthrough module. See the
[native API guide](guides/native-api.md).

## Model — the typed everyday layer

`client.model` hand-wraps the high-frequency API with proper types, handles,
enums, and docstrings. Anything not yet wrapped is one attribute chain away
through `client.api`, and `client.raw_model` is the ultimate escape hatch.

## Computation modules — no COM dependency

`fiber` and `yield_surface` are pure NumPy. They depend only on each other and
on NumPy, never on COM, so they are unit-tested against analytical solutions on
any platform and can be reused outside a SAP2000 session.
