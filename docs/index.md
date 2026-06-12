# Sap2000py

A Pythonic wrapper around the SAP2000 Open API (OAPI). It turns the COM-based
OAPI into a typed, explicit, well-behaved Python library.

!!! warning "1.0 is a breaking rewrite"
    The API is completely different from the `0.1.x` series. See
    [Migrating from v0](migration-from-v0.md).

## What it gives you

- **An explicit connection.** `SapClient.launch()` / `.attach()` instead of an
  import-time singleton. Importing the package does nothing to SAP2000.
- **One place that checks every call.** The `ComGateway` validates every OAPI
  return code and raises a typed exception — no more silent failures.
- **A typed everyday API.** `client.model.points.add(0, 0, 0)` with handles,
  enums, and units context managers.
- **A full escape hatch.** Anything not yet wrapped is reachable through
  `client.api.<Object>.<Method>(...)` with the same error handling.
- **Engineering modules.** Section geometry, fiber moment-curvature, yield
  surfaces, parametric optimization, and a bridge component library — each
  behind an optional extra so the core stays light.

## Install

```bash
pip install sap2000py            # core
pip install "sap2000py[all]"     # every optional feature
```

SAP2000 must be installed locally; the COM API is Windows-only.

## Next

- [Quickstart](quickstart.md)
- [Migrating from v0](migration-from-v0.md)
- [Units](guides/units.md)
