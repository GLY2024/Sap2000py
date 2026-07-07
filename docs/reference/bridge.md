# Bridge API

The `sap2000py.bridge` package — parametric components, auto-connection, and
system assemblers. See the [bridge guide](../guides/bridge.md) for an overview.

## Component protocol

::: sap2000py.bridge.component.BridgeComponent
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

## Components

::: sap2000py.bridge.components.foundation.Foundation
    options:
      show_root_heading: true
      heading_level: 3

::: sap2000py.bridge.components.pier.Pier
    options:
      show_root_heading: true
      heading_level: 3

::: sap2000py.bridge.components.bearing.Bearing
    options:
      show_root_heading: true
      heading_level: 3

::: sap2000py.bridge.components.isolators.LeadRubberBearing
    options:
      show_root_heading: true
      heading_level: 3

::: sap2000py.bridge.components.isolators.FrictionPendulumBearing
    options:
      show_root_heading: true
      heading_level: 3

::: sap2000py.bridge.components.girder.Girder
    options:
      show_root_heading: true
      heading_level: 3

## Auto-connection

::: sap2000py.bridge.connect
    options:
      show_root_heading: false
      heading_level: 3
      members_order: source

## System assemblers

::: sap2000py.bridge.systems.ContinuousGirderBridge
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

::: sap2000py.bridge.systems.BridgeBuild
    options:
      show_root_heading: true
      heading_level: 3

## Presets

::: sap2000py.bridge.presets
    options:
      show_root_heading: false
      heading_level: 3
      members_order: source
