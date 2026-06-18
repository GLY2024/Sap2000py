"""sap2000py — a Pythonic SAP2000 OAPI wrapper.

Importing this package has **no side effects**: it does not touch COM or start
SAP2000. Create a connection explicitly::

    from sap2000py import SapClient, Units

    with SapClient.launch(visible=False) as client:
        client.model.files.new_blank(units=Units.KN_M_C)
        client.model.points.add(0, 0, 0)
"""

from __future__ import annotations

from .client import SapClient
from .discovery import Installation, installations
from .enums import (
    DOF,
    DOF_NAMES,
    ItemType,
    ItemTypeElm,
    LoadPatternType,
    MatType,
    Units,
    dof_mask,
    to_dof_mask,
)
from .errors import (
    MissingDependencyError,
    SapAnalysisError,
    SapApiError,
    SapComError,
    SapCompatibilityError,
    SapConnectionError,
    SapError,
    SapModelLockedError,
    SapNameNotFoundError,
    SapVersionMismatchError,
    SapVersionNotFoundError,
)
from .gateway import ErrorPolicy
from .handles import (
    AreaHandle,
    CableHandle,
    Handle,
    SolidHandle,
    TendonHandle,
)
from .model.analysis import AnalysisReport
from .model.frame_sections import FrameSectionHandle
from .model.frames import FrameHandle
from .model.groups import GroupHandle
from .model.link_props import LinkPropHandle
from .model.links import LinkHandle
from .model.materials import MaterialHandle
from .model.points import PointHandle
from .model.results import ResultTable

__version__ = "1.0.0a1"

__all__ = [  # noqa: RUF022 - grouped by category for readability, not sorted
    "__version__",
    # connection
    "SapClient",
    "Installation",
    "installations",
    "ErrorPolicy",
    # enums / values
    "Units",
    "ItemType",
    "ItemTypeElm",
    "MatType",
    "LoadPatternType",
    "DOF",
    "DOF_NAMES",
    "dof_mask",
    "to_dof_mask",
    # results
    "ResultTable",
    "AnalysisReport",
    # errors
    "SapError",
    "SapConnectionError",
    "SapComError",
    "SapApiError",
    "SapModelLockedError",
    "SapNameNotFoundError",
    "SapAnalysisError",
    "SapVersionNotFoundError",
    "SapVersionMismatchError",
    "SapCompatibilityError",
    "MissingDependencyError",
    # handles
    "Handle",
    "PointHandle",
    "FrameHandle",
    "CableHandle",
    "TendonHandle",
    "AreaHandle",
    "SolidHandle",
    "LinkHandle",
    "MaterialHandle",
    "FrameSectionHandle",
    "LinkPropHandle",
    "GroupHandle",
]
