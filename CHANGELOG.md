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
- Remaining optional modules behind extras: `sections` (DXF/shapely geometry),
  `optimize`, and a redesigned `bridge` component library.

### Removed
- The 5,465-line `SapObj.py` direct-passthrough layer (replaced by `client.api`).
- The forced-singleton `SapMeta` metaclass and import-time COM activation.
- Known latent bugs carried by the old code (e.g. the `Nonliear` `NameError`
  in `SapSection.Damper`, the `Pine`/`Line` constraint typo, and the
  `KeCoupled` branch logic error).
