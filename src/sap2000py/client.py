"""Connection lifecycle: launch, attach, and own a SAP2000 instance.

This replaces the old import-time ``Saproject`` singleton. A :class:`SapClient`
is an ordinary object you create explicitly; importing the package does nothing
to SAP2000. ``comtypes`` is imported lazily inside :meth:`launch`/:meth:`attach`
so the package stays importable on any platform (the pure-Python computation
modules don't need COM).
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

from loguru import logger

from .discovery import Installation, _major, _version_key, installations
from .enums import Units
from .errors import SapConnectionError, SapVersionMismatchError, SapVersionNotFoundError
from .gateway import COMError, ComGateway, ErrorPolicy
from .model import Model
from .native import NativeApi

_PROGID = "CSI.SAP2000.API.SapObject"


def _format_installation(installation: Installation) -> str:
    version = installation.version or "unknown version"
    return f"{version} at {installation.path}"


def _select_installation(version: str) -> tuple[int, Installation]:
    requested_major = _major(version)
    available = installations()
    matches = [item for item in available if item.major == requested_major]
    if not matches:
        listed = ", ".join(_format_installation(item) for item in available) or "none"
        raise SapVersionNotFoundError(
            f"SAP2000 major version {requested_major} was not found. "
            f"Available installations: {listed}."
        )

    known = [item for item in matches if _version_key(item.version) is not None]
    if known:
        highest_key = max(_version_key(item.version) or () for item in known)
        highest = [item for item in known if _version_key(item.version) == highest_key]
        if len(highest) == 1:
            return requested_major, highest[0]
        listed = ", ".join(_format_installation(item) for item in highest)
        raise SapVersionNotFoundError(
            f"SAP2000 major version {requested_major} has multiple installations "
            f"with the highest discovered version. Use program_path= to choose one: {listed}."
        )

    if len(matches) == 1:
        return requested_major, matches[0]

    listed = ", ".join(_format_installation(item) for item in matches)
    raise SapVersionNotFoundError(
        f"SAP2000 major version {requested_major} has no discoverable full version. "
        f"Matching installations: {listed}."
    )


def _make_helper() -> Any:
    """Create and return the SAP2000 OAPI ``cHelper`` (lazy comtypes import)."""
    import comtypes
    import comtypes.client

    helper = comtypes.client.CreateObject("SAP2000v1.Helper")
    return helper.QueryInterface(comtypes.gen.SAP2000v1.cHelper)


class SapClient:
    """Owns one COM connection to a SAP2000 instance.

    Construct via :meth:`launch` or :meth:`attach` rather than directly. Use as
    a context manager to guarantee cleanup of a launched instance::

        with SapClient.launch(visible=False) as client:
            client.model.files.new_blank(units=Units.KN_M_C)
    """

    def __init__(
        self,
        sap_object: Any,
        *,
        owns_process: bool,
        sap_model: Any | None = None,
        policy: ErrorPolicy = ErrorPolicy.RAISE,
    ) -> None:
        self._object = sap_object
        self._owns_process = owns_process
        self._closed = False
        sap_model = sap_object.SapModel if sap_model is None else sap_model
        self._gateway = ComGateway(sap_model, policy=policy)
        self.model = Model(self._gateway)
        self.api = NativeApi(self._gateway, node=sap_model)

    # -- construction -------------------------------------------------------

    @classmethod
    def launch(
        cls,
        *,
        visible: bool = True,
        version: str | None = None,
        program_path: str | Path | None = None,
        new_model: bool = True,
        units: Units = Units.KN_M_C,
        policy: ErrorPolicy = ErrorPolicy.RAISE,
    ) -> SapClient:
        """Start a new SAP2000 process and connect to it.

        Parameters
        ----------
        visible:
            Show the SAP2000 GUI. Use ``False`` for headless/batch runs.
        version:
            SAP2000 major version to launch, for example ``"25"``. The highest
            discovered patch for that major version is used.
        program_path:
            Path to a specific ``SAP2000.exe`` to launch; otherwise the
            registered version is used.
        new_model:
            Initialize a blank model in ``units`` after starting.
        """
        if version is not None and program_path is not None:
            raise ValueError("version and program_path are mutually exclusive.")

        requested_major: int | None = None
        if version is not None:
            requested_major, installation = _select_installation(version)
            program_path = installation.path

        helper = _make_helper()
        try:
            if program_path is not None:
                sap_object = helper.CreateObject(str(program_path))
            else:
                sap_object = helper.CreateObjectProgID(_PROGID)
        except (OSError, COMError) as exc:
            raise SapConnectionError(
                f"Cannot start a new SAP2000 instance"
                f"{f' from {program_path}' if program_path else ''}."
            ) from exc

        client = cls(sap_object, owns_process=True, policy=policy)
        client._gateway.call(
            sap_object.ApplicationStart, int(units), visible, "", api_name="ApplicationStart"
        )
        if requested_major is not None:
            actual_major = client.model.sap_version_major
            if actual_major != requested_major:
                client._gateway.call(sap_object.ApplicationExit, False, api_name="ApplicationExit")
                client._closed = True
                raise SapVersionMismatchError(requested_major, actual_major)
        if new_model:
            client.model.files.new_blank(units=units)
        logger.debug("Launched SAP2000 (visible={}).", visible)
        return client

    @classmethod
    def attach(cls, *, policy: ErrorPolicy = ErrorPolicy.RAISE) -> SapClient:
        """Attach to an already-running SAP2000 instance.

        Raises :class:`~sap2000py.errors.SapConnectionError` if none is found.
        This never silently launches a new instance — that ambiguity was a bug
        source in the old code. Use :meth:`attach_or_launch` if you want the
        fallback explicitly.
        """
        helper = _make_helper()
        try:
            sap_object = helper.GetObject(_PROGID)
        except (OSError, COMError) as exc:
            raise SapConnectionError("No running SAP2000 instance to attach to.") from exc
        if sap_object is None:
            raise SapConnectionError("No running SAP2000 instance to attach to.")
        logger.debug("Attached to running SAP2000 instance.")
        return cls(sap_object, owns_process=False, policy=policy)

    @classmethod
    def attach_or_launch(
        cls,
        *,
        version: str | None = None,
        launch_on_version_mismatch: bool = False,
        **launch_kwargs: Any,
    ) -> SapClient:
        """Attach to a running instance, or launch a new one if none exists."""
        if version is not None and launch_kwargs.get("program_path") is not None:
            raise ValueError("version and program_path are mutually exclusive.")

        try:
            client = cls.attach(policy=launch_kwargs.get("policy", ErrorPolicy.RAISE))
        except SapConnectionError:
            logger.info("No running instance; launching a new one.")
            return cls.launch(version=version, **launch_kwargs)

        if version is None:
            return client
        requested_major = _major(version)
        actual_major = client.model.sap_version_major
        if actual_major == requested_major:
            return client
        if not launch_on_version_mismatch:
            raise SapVersionMismatchError(requested_major, actual_major)
        logger.info(
            "Running SAP2000 major version {} does not match requested {}; launching a new one.",
            actual_major,
            requested_major,
        )
        return cls.launch(version=version, **launch_kwargs)

    @staticmethod
    def installations() -> list[Installation]:
        """Return discovered SAP2000 installations."""
        return installations()

    # -- accessors ----------------------------------------------------------

    @property
    def raw_model(self) -> Any:
        """The raw comtypes ``cSapModel`` — the ultimate escape hatch."""
        return self._gateway.model

    @property
    def raw_object(self) -> Any:
        """The raw comtypes ``cOAPI`` application object."""
        return self._object

    @property
    def version(self) -> str:
        """SAP2000 program version string. Wraps ``GetVersion``."""
        return self.model.sap_version

    @property
    def error_policy(self) -> ErrorPolicy:
        """How non-zero OAPI statuses are handled (RAISE or WARN)."""
        return self._gateway.policy

    @error_policy.setter
    def error_policy(self, policy: ErrorPolicy) -> None:
        self._gateway.policy = policy

    # -- teardown -----------------------------------------------------------

    def close(self, *, save: str | Path | None = None) -> None:
        """Close the connection, saving first if ``save`` is given.

        Only a launched instance's process is exited; an attached instance is
        left running (we just drop our references).

        If exiting an owned process fails, the failure is **raised** and the
        client is left open and retryable — a swallowed exit can leave a hidden
        SAP2000 process or license alive while the caller believes cleanup
        succeeded. The client is marked closed only once the process is known
        gone, so a later ``close()`` can retry rather than silently no-op.
        """
        if self._closed:
            return
        if save is not None:
            self.model.files.save(save)
        if self._owns_process:
            # Mark closed only after a successful exit: a failed ApplicationExit
            # must stay observable and retryable, not become a silent no-op.
            self._gateway.call(self._object.ApplicationExit, False, api_name="ApplicationExit")
        self._closed = True

    def __enter__(self) -> SapClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Only tear down processes we started; attached instances stay alive.
        if not self._owns_process:
            return
        try:
            self.close()
        except Exception as cleanup_exc:
            # Never let a teardown failure mask an exception from the with-body;
            # surface it only when the body left cleanly.
            if exc is None:
                raise
            logger.warning("ApplicationExit failed during context exit: {}", cleanup_exc)
