# The native API escape hatch

The typed `model` facade wraps the high-frequency OAPI. It does not — and never
will — wrap all ~2,000 OAPI methods by hand; that was the old code's mistake.
Instead, the *entire* OAPI is always reachable through `client.api`, with the
same return-code checking and error handling.

## How it works

`client.api` is a dynamic proxy. Attribute access walks the COM object tree and
method calls are routed through the same `ComGateway` the typed layer uses:

```python
# Equivalent to model.points.add(0, 0, 0), but spelled in raw OAPI terms:
name = client.api.PointObj.AddCartesian(0.0, 0.0, 0.0, "", "", "Global", False, 0)

# Direct-value methods work too:
count = client.api.PointObj.Count()
```

Arguments are passed through verbatim, in the exact order the OAPI expects,
including placeholders for ``[in, out]`` parameters (pass ``""``, ``0``, etc.).
This mirrors the calling convention from the CSI OAPI documentation, so you can
follow the official docs directly.

## What you get and don't get

- **You get** centralized error handling: a non-zero status raises
  `SapApiError`, COM failures raise `SapComError`, and the call is logged at
  `trace` level like any other.
- **You don't get** static type checking or guaranteed editor completion.
  A generated `native.pyi` stub provides *best-effort* completion (regenerate
  with `python -m sap2000py._stubgen.gen_native_stubs`), but the proxy is
  resolved dynamically at runtime.

If you find yourself calling the same native method often, that is a good
candidate to wrap in the typed `model` layer.

## The ultimate escape hatch

If even the proxy is in your way (you need the raw comtypes object, an unusual
calling convention, or to inspect the COM interface), reach straight for it:

```python
raw = client.raw_model       # the comtypes cSapModel
raw.PointObj.AddCartesian(0, 0, 0, "", "", "Global", False, 0)   # no gateway
```

At that point you are on your own for return-code checking.
