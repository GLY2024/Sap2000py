# Sap2000py

A Pythonic wrapper around the SAP2000 Open API (OAPI) for structural and
bridge engineering. It turns the COM-based OAPI into a typed, explicit,
well-behaved Python library.

> **⚠️ 1.0 is a breaking rewrite.** The API is completely different from the
> `0.1.x` series. If you depend on the old `Saproject()` singleton, pin
> `sap2000py==0.1.3` or use the `v0.1.3-legacy` tag while you migrate. See
> [`docs/migration-from-v0.md`](docs/migration-from-v0.md).

## Why the rewrite

The `0.1.x` codebase worked but had structural problems that made it hard to
trust and extend:

- **Importing the package started SAP2000.** A singleton metaclass activated a
  COM connection at import time.
- **No central error handling.** Roughly a third of methods never checked the
  OAPI return code; some logged an error and kept going.
- **~9,000 lines of hand-written passthrough**, with copy-pasted boilerplate
  and latent bugs that could only fail at call time (the code had no tests).
- **The bridge layer was welded to the singleton** (72 direct `Saproject()`
  calls) and hard-coded engineering parameters inline.

`1.0` keeps the genuinely valuable domain knowledge and rebuilds the
foundation.

## Design at a glance

```python
from sap2000py import SapClient, Units, DOF

with SapClient.launch(visible=False) as client:
    m = client.model
    m.files.new_blank(units=Units.KN_M_C)

    c40 = m.materials.add_concrete("C40", code="JTG")
    sec = m.frame_sections.add_rectangle("Pier", material=c40, depth=2.0, width=1.0)

    p1 = m.points.add(0, 0, 0)
    p2 = m.points.add(0, 0, 10)
    m.frames.add_by_points(p1, p2, section=sec)
    m.points.set_restraints(p1, dof=DOF.fixed())

    m.analysis.run(cases=["MODAL"])
    print(m.results.modal_periods().to_pandas())
```

Anything not yet wrapped by the typed `model` facade is always reachable
through the full dynamic proxy, with the same error handling:

```python
name = client.api.PointObj.AddCartesian(0, 0, 0)   # raw OAPI, return code checked
raw = client.raw_model                              # ultimate escape hatch
```

The package is fully typed and ships a [PEP 561](https://peps.python.org/pep-0561/)
`py.typed` marker, so mypy/Pyright check your code and editors autocomplete
methods, handles, and enums (the selectable `Units`, `ItemType`, ...) — including
a generated stub for the dynamic `client.api` proxy. See the
[typing guide](docs/guides/typing.md).

## Installation

```bash
pip install sap2000py                 # core (Windows, needs SAP2000 installed)
pip install "sap2000py[sections]"     # + DXF / shapely section geometry
pip install "sap2000py[fiber]"        # + fiber moment-curvature
pip install "sap2000py[bridge]"       # + bridge component library
pip install "sap2000py[all]"          # everything
```

SAP2000 itself must be installed locally; the COM API is Windows-only.

## Layout

| Module | Purpose |
| --- | --- |
| `sap2000py.client` / `gateway` / `native` | Connection lifecycle + the COM call chokepoint |
| `sap2000py.model` | Typed domain facade (the everyday API) |
| `sap2000py.sections` | Complex section geometry (DXF, shapely, templates) |
| `sap2000py.fiber` | Fiber sections + moment-curvature analysis |
| `sap2000py.yield_surface` | P-M-M yield surfaces |
| `sap2000py.optimize` | Parametric studies / optimization |
| `sap2000py.bridge` | Bridge components, auto-connection, and systems |

## Documentation

The docs are a MkDocs (Material) site under [`docs/`](docs/) with API reference
auto-generated from docstrings via mkdocstrings. They are wired to deploy two
ways out of the box:

- **GitHub Pages** — the [`Docs` workflow](.github/workflows/docs.yml) builds
  and publishes on every push to `main` (enable Pages → "GitHub Actions" in repo
  settings).
- **Read the Docs** — [`.readthedocs.yaml`](.readthedocs.yaml) builds the same
  site; just import the repo on readthedocs.org.

Build and preview locally:

```bash
uv sync --extra docs
uv run mkdocs serve        # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict
```

## Development

```bash
uv sync --all-extras --dev
uv run pytest                 # unit tests (no SAP2000 needed)
uv run pytest --sap           # + integration tests (real SAP2000)
uv run ruff check .
uv run mypy
```

## License

MIT. See [LICENSE](LICENSE).
