# Connecting to SAP2000

A `SapClient` owns one COM connection. Create it explicitly — importing the
package never touches COM.

## Launch a new instance

```python
from sap2000py import SapClient, Units

with SapClient.launch(visible=True, units=Units.KN_M_C) as client:
    ...
```

`launch()` starts a new SAP2000 process. Options:

- `visible=False` for headless/batch runs.
- `program_path=...` to launch a specific `SAP2000.exe`.
- `new_model=False` to skip initializing a blank model.

A launched instance is **owned** by the client: leaving the `with` block (or
calling `close()`) exits SAP2000.

## Attach to a running instance

```python
client = SapClient.attach()             # raises if nothing is running
client = SapClient.attach_or_launch()   # attach, else launch a new instance
```

`attach()` never silently launches a new instance — that ambiguity was a bug
source in the old code. An attached instance is **not** owned: `close()` just
drops the connection and leaves SAP2000 running.

## Closing and saving

```python
client.close(save="model.sdb")   # save, then (if launched) exit
```

## Error policy

By default any non-zero OAPI status raises `SapApiError`. For an exploratory
session you can downgrade to logged warnings:

```python
from sap2000py import ErrorPolicy
client.error_policy = ErrorPolicy.WARN
```

## Escape hatches

```python
client.version       # SAP2000 version string
client.raw_model     # the raw comtypes cSapModel
client.raw_object    # the raw cOAPI application object
client.api           # the full dynamic OAPI proxy
```
