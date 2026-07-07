# Seismic analysis

Sap2000py keeps the seismic workflow explicit: define the model, define the
seismic input, create SAP2000 load cases, run, then read results. The package
does not hide units or analysis choices behind a project object.

## Ground motions

Ground-motion records are normalized to acceleration in `g`:

```python
from sap2000py.seismic import read_suite

suite = read_suite("motions", pattern="*.csv")
print(suite.summary().rows())
```

Supported inputs include PEER-style `NPTS/DT` files, one-column files with
`dt=`, two-column `(time, acceleration)` files, and CSV. Unit detection is
strict: pass `unit="g"` / `"gal"` / `"cm/s2"` / `"m/s2"` when the file header
does not say what the acceleration unit is.

When a record is written to SAP2000 as a time-history function, the values stay
in `g`. The conversion to model length units per second squared is applied in
the load-case scale:

```python
from sap2000py import HistoryLoad
from sap2000py.seismic import gravity

function = record.to_function(model)
load = HistoryLoad(function=function, load="U1", scale=gravity(model.current_units))
```

## Response spectrum

Use code spectra when SAP2000 already exposes the code you need. Use a user
spectrum for JTG/T 2231-01-2020 or project-specific spectra:

```python
from sap2000py import SpectrumLoad
from sap2000py.seismic import jtg2231_spectrum

design = jtg2231_spectrum(peak_accel=0.2, tg=0.45)
model.functions.rs.add_user("E2", design.periods, design.values, damping=design.damping)
model.loads.cases.add_modal_eigen("MODAL", num_modes=12)
model.loads.cases.add_response_spectrum(
    "RS_U1",
    loads=[SpectrumLoad("U1", "E2")],
    modal_case="MODAL",
)
```

Then save, run `["MODAL", "RS_U1"]`, select `RS_U1`, and read base reactions,
frame forces, link forces, or other result tables.

## Time history

The S4 runner composes with ordinary model-building code. It creates one
time-history case per record, runs it, extracts EDPs immediately, and writes
checkpoints so an interrupted batch can resume:

```python
from sap2000py import RayleighDamping
from sap2000py.seismic import NlthConfig, bridge_edps, run_nlth_batch

config = NlthConfig(
    damping=RayleighDamping.from_periods(0.3, 1.5, 0.05),
    gravity_case="GRAV",
)
results = run_nlth_batch(
    model,
    suite,
    edps=bridge_edps(build, dof="U1"),
    config=config,
    workdir=Path("nlth_work"),
)
```

## Damping and integration

Use modal damping for response-spectrum and FNA cases. Use explicit
`RayleighDamping` for direct integration so the mass/stiffness coefficients or
period targets are visible in code.

`TimeIntegration.hht()` is the default direct-integration payload because it is
stable for typical bridge NLTH studies. Use `newmark()` or `wilson()` when you
need to match an existing calculation.

## FNA or direct integration

| Choice | Use when | Avoid when |
| --- | --- | --- |
| FNA / modal history | Nonlinearity is limited to link elements such as isolators; Ritz vectors include acceleration and link loads. | Plastic hinges or material/frame nonlinearity control the response. |
| Direct integration | Hinges, nonlinear static initial states, or broad nonlinear behavior matter. | You only need fast link-isolator sweeps and have a calibrated Ritz basis. |

For bridge-isolator studies, FNA can be useful for screening. For ductile pier
hinge studies, use direct integration.
