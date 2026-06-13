# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [1.0.0a1] - Unreleased

### ⚠️ Breaking — full rewrite

`1.0` is a ground-up rewrite with a new, Pythonic API. It is **not**
backwards compatible with the `0.1.x` series. Code written against the old
`Saproject()` singleton must be migrated; see `docs/migration-from-v0.md`.

The frozen `0.1.3` sources remain available under `legacy/` and at the
`v0.1.3-legacy` git tag for reference and temporary use.

### Added
- `SapClient` — an explicit connection object replacing the import-time
  `Saproject` singleton. Supports `launch()`, `attach()`, and use as a context
  manager. Importing the package no longer starts SAP2000.
- `ComGateway` — a single chokepoint for every OAPI call that checks the
  return code, unpacks comtypes by-ref out-parameters, and raises typed
  exceptions (`SapApiError`, `SapComError`, `SapConnectionError`).
- `client.api` — a thin dynamic proxy (`NativeApi`) exposing the *entire*
  OAPI with centralized error handling, for any method not yet wrapped.
- `client.model` — a hand-written, typed domain facade for the high-frequency
  API:
  - `files` (new/open/save), `points` (add/restrain/query),
    `materials` (code-based + isotropic, incl. the Chinese-code library ported
    from the old `Common_Material_Set`), `frame_sections`
    (rectangle/circle/general/modifiers), `frames`
    (add/section/releases/local-axes/output-stations/grouping), `groups`,
    `constraints` (Body/Equal joint constraints), `link_props` + `links`
    (linear link properties and two-joint link elements, plus point springs),
    `loads` (patterns + cases, collapsing the old 13 `load_*` classes into
    parameterized methods), `analysis` (run-flags/run/status), and `results`.
  - `ResultTable` — column-oriented results with `.rows()` and an optional
    `.to_pandas()` (behind the `tables` extra).
- `Units` enum + `model.units(...)` restoring context manager.
- `sap2000py.fiber` — fiber moment-curvature analysis (pure NumPy, no COM):
  `ManderConcrete` (confined/unconfined) and `BilinearSteel` constitutive
  models, `FiberSection` discretization, and a `moment_curvature` solver with
  equal-energy `bilinearize()`. Verified against the analytical elastic `E·I`
  solution.
- `sap2000py.yield_surface` — `pm_interaction` axial-moment interaction
  envelopes built on fiber sections.
- `sap2000py.bridge` — the M4 bridge component library: `BridgeComponent` with
  explicit `build(model)` injection (replacing the old 72 `Saproject()`
  singleton calls), the `Foundation` / `Pier` / `Bearing` / `Girder`
  components with named anchors, `snap_connect` auto-connection
  (Body / Equal / rigid-link strategies), the `ContinuousGirderBridge` system
  assembler with `from_yaml`, and engineering parameters externalized to
  `bridge/data/*.yaml` (e.g. `bearing_preset`).
- Full static-typing support: a [PEP 561](https://peps.python.org/pep-0561/)
  `py.typed` marker so downstream `mypy`/Pyright check against the library's
  types, plus a generated `native.pyi` stub giving editor completion for the
  dynamic `client.api` proxy (regenerate + audit via
  `python -m sap2000py._stubgen.gen_native_stubs`).
- Remaining optional modules behind extras: `sections` (DXF/shapely geometry)
  and `optimize`.

### Fixed
- `client.api` no longer silently ignores a failed status-only OAPI mutation
  (e.g. `File.Save`, `Analyze.RunAnalysis`): the gateway now treats a bare
  integer return as a status by default — raising on non-zero, with a curated
  allow-set for genuine value-getters (`Count*`, `GetPresentUnits`, ...) — so a
  failure can't pass as success.
- `SapClient.close()` no longer marks the client closed when `ApplicationExit`
  fails; the failure is raised and the teardown stays retryable instead of
  leaking a hidden SAP2000 process or license.

### Removed
- The 5,465-line `SapObj.py` direct-passthrough layer (replaced by `client.api`).
- The forced-singleton `SapMeta` metaclass and import-time COM activation.
- Known latent bugs carried by the old code (e.g. the `Nonliear` `NameError`
  in `SapSection.Damper`, the `Pine`/`Line` constraint typo, and the
  `KeCoupled` branch logic error).
