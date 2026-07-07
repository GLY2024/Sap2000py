# Fragility workflows

Fragility fitting is split into two layers:

- SAP2000 demand collection through `run_nlth_batch`, `run_ida`, or `run_msa`.
- Pure NumPy fitting in `sap2000py.seismic.fragility`.

## Cloud analysis

Cloud analysis fits a probabilistic seismic demand model:

```python
from sap2000py.seismic import cloud_fragility, demands, fit_psdm

im, edp = demands(results, im="pga", edp="P1_drift_U1")
psdm = fit_psdm(im, edp)
curve = cloud_fragility(psdm, capacity=0.02, beta_capacity=0.25)
print(curve.theta, curve.beta)
```

The fitted model is `ln(EDP) = ln_a + b ln(IM)` with conditional dispersion
`beta_D|IM`. `cloud_fragility` maps a capacity threshold into an IM-space
lognormal curve.

## IDA

`run_ida` reuses the NLTH runner for a sequence of intensity levels. Fixed
levels are enough for most repeatable comparisons; hunting can be enabled for a
collapse-focused study.

```python
from sap2000py.seismic.ida import run_ida

curves = run_ida(model, suite, edp=edp, config=config, levels=[0.1, 0.2, 0.4], workdir=workdir)
```

Use `ida_fragility` on collapse IM values when the failure definition is
collapse, not ordinary demand exceedance.

## MSA

`run_msa` takes stripes `(level, suite)` and scales each record to the target
IM before running the batch. `msa_fragility` fits the lognormal curve from
exceedance counts and uses SciPy through the existing `optimize` extra.

## Damage states from MC

For ductile pier studies, damage states can come from a moment-curvature result:

```python
from sap2000py.seismic.hinges import damage_states_from_mc

damage = damage_states_from_mc(mc, mu=(1.0, 2.0, 4.0, None))
```

The returned thresholds are curvature-ductility thresholds. Convert them to the
EDP used in the fragility fit before mixing them with drift or deformation
demands.
