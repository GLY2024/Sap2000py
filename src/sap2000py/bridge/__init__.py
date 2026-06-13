"""Bridge component library, auto-connection, and system assemblers.

Requires the ``bridge`` extra only for YAML configs
(``pip install 'sap2000py[bridge]'``); the components themselves are pure Python.

A component is *pure data* until you call ``build(model)``; it then creates its
objects in that model and exposes named ``anchors`` that
:func:`~sap2000py.bridge.connect.snap_connect` ties together::

    from sap2000py.bridge import ContinuousGirderBridge

    bridge = ContinuousGirderBridge(
        "B1",
        spans=[40, 40, 40],
        pier_height=12.0,
        girder_section="Girder",
        pier_section="Pier",
        bearing_stiffness=[2e5, 2e5, 2e9, 0, 0, 0],
    )
    bridge.build(model)
"""

from __future__ import annotations

from .component import BridgeComponent
from .components.bearing import Bearing
from .components.foundation import Foundation
from .components.girder import Girder
from .components.pier import Pier
from .connect import Connection, snap_connect
from .presets import bearing_preset, bearing_presets
from .systems import BridgeBuild, ContinuousGirderBridge

__all__ = [
    "Bearing",
    "BridgeBuild",
    "BridgeComponent",
    "Connection",
    "ContinuousGirderBridge",
    "Foundation",
    "Girder",
    "Pier",
    "bearing_preset",
    "bearing_presets",
    "snap_connect",
]
