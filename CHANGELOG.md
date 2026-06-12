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
  API (files, points, frames, materials, sections, loads, analysis, results).
- `Units` enum + `model.units(...)` restoring context manager.
- Optional modules behind extras: `sections`, `fiber`, `yield_surface`,
  `optimize`, and a redesigned `bridge` component library.

### Removed
- The 5,465-line `SapObj.py` direct-passthrough layer (replaced by `client.api`).
- The forced-singleton `SapMeta` metaclass and import-time COM activation.
- Known latent bugs carried by the old code (e.g. the `Nonliear` `NameError`
  in `SapSection.Damper`, the `Pine`/`Line` constraint typo, and the
  `KeCoupled` branch logic error).
