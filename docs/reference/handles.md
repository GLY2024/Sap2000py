# Handles

A live handle is a reference to an object in SAP2000 by name. It stores no model
state and never caches object properties; reading or mutating through a handle
round-trips to SAP2000 every time.

Create live handles through managers:

```python
p = m.points.add(0, 0, 0)
same_point = m.points.ref("P1")
checked = m.points["P1"]        # validates by GetNameList
```

Handle equality compares only the handle type and `name`; `_owner` is not part
of equality. Same-named handles from different `SapClient` or model instances
therefore compare equal, but each manager's `ref()` rejects handles already
bound to another manager/model unless you pass `.name` explicitly.

Top-level imports such as `from sap2000py import PointHandle` are supported for
typing. `sap2000py.handles` contains only the base class, `as_name()`, and
unwrapped name handles for nouns that do not yet have managers.

## Base helpers

::: sap2000py.handles.Handle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source
      show_if_no_docstring: true

::: sap2000py.handles.as_name
    options:
      show_root_heading: true
      heading_level: 2

## Live handles

::: sap2000py.model.points.PointHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: sap2000py.model.frames.FrameHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: sap2000py.model.materials.MaterialHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: sap2000py.model.frame_sections.FrameSectionHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: sap2000py.model.link_props.LinkPropHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: sap2000py.model.links.LinkHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: sap2000py.model.groups.GroupHandle
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

## Unwrapped name handles

`CableHandle`, `TendonHandle`, `AreaHandle`, and `SolidHandle` are typed name
wrappers for nouns that are not yet exposed as live-handle managers. Use
`client.api` or `client.raw_model` for their operations.

::: sap2000py.handles.CableHandle
    options:
      show_root_heading: true
      heading_level: 2

::: sap2000py.handles.TendonHandle
    options:
      show_root_heading: true
      heading_level: 2

::: sap2000py.handles.AreaHandle
    options:
      show_root_heading: true
      heading_level: 2

::: sap2000py.handles.SolidHandle
    options:
      show_root_heading: true
      heading_level: 2
