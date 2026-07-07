# Parametric studies

`sap2000py.optimize` provides a small checkpointed driver for SAP2000 parameter
studies. It does not define an optimization framework; it only repeats the
same build-run-collect sequence for a grid of parameters.

```python
from sap2000py.optimize import ParameterGrid, run_study

grid = ParameterGrid({"pier_height": [8.0, 12.0], "bearing_type": ["ductile", "isolated"]})
```

`ParameterGrid.combos()` yields dictionaries in axis order. You can also pass
an explicit sequence of mappings to `run_study`.

## Driver shape

```python
def build(params, model):
    bridge = make_bridge(params)
    bridge.build(model)
    model.loads.cases.add_modal_eigen("MODAL", num_modes=12)


def collect(params, model):
    model.results.select_output(cases=["MODAL"])
    periods = model.results.modal_periods()
    return {"t1": periods["period"][0]}


table = run_study(
    client,
    grid,
    build=build,
    collect=collect,
    workdir=Path("study"),
    run_cases=["MODAL"],
)
```

For each parameter set the driver creates a blank model, calls `build`, saves a
`case_<hash>.sdb` file, runs the requested cases, calls `collect`, and appends
one row to `study.jsonl`.

The parameter hash is deterministic and based on sorted parameter items, so it
is stable across Python processes. With `resume=True`, existing rows in
`study.jsonl` are returned without rebuilding those cases.

## Ductile vs isolated recipe

Use the same bridge geometry and swap only the bearing maker:

```python
from sap2000py import LeadRubberBearing
from sap2000py.bridge import Bearing

def bearing_maker(kind):
    def make(name, x, y, z):
        if kind == "isolated":
            return LeadRubberBearing(
                name,
                x,
                y,
                z,
                vertical_stiffness=2.0e10,
                shear_stiffness=2.0e5,
                yield_force=350.0,
            )
        return Bearing(name, x, y, z, stiffness=[1.0e9, 1.0e9, 2.0e10, 0, 0, 0])

    return make
```

Then collect the same metrics for both designs: fundamental period, peak pier
drift, bearing deformation, base shear, or a fragility parameter computed by a
nested `run_nlth_batch` call inside `collect`.
