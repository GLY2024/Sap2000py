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
- `version="25"` to launch the highest discovered SAP2000 25.x installation.
- `program_path=...` to launch a specific `SAP2000.exe`.
- `new_model=False` to skip initializing a blank model.

A launched instance is **owned** by the client: leaving the `with` block (or
calling `close()`) exits SAP2000.

## Select a SAP2000 version

```python
from sap2000py import SapClient, installations

for item in installations():
    print(item.version, item.path)

with SapClient.launch(version="25", visible=False) as client:
    assert client.version.startswith("25.")
```

`version=` and `program_path=` are mutually exclusive. Version discovery treats
installation paths only as candidates; the version itself comes from the
executable metadata or an explicit registry value. After SAP2000 starts,
`launch(version=...)` reads the connected program version before creating a new
model. If the process is not the requested major version, it exits that process
and raises `SapVersionMismatchError`. If discovery finds multiple paths tied for
the highest known patch version, use `program_path=` to choose explicitly.

## Attach to a running instance

```python
client = SapClient.attach()             # raises if nothing is running
client = SapClient.attach_or_launch(version="25")   # attach matching version, else launch
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
