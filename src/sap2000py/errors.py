"""Exception hierarchy for sap2000py.

Every failure path in the library raises one of these. This is a deliberate
break from the old code, which frequently logged an error and continued with
invalid state. Fail fast, fail typed.
"""

from __future__ import annotations

from typing import Any


class SapError(Exception):
    """Base class for every error raised by sap2000py."""


class SapConnectionError(SapError):
    """Raised when launching or attaching to a SAP2000 instance fails."""


class SapVersionNotFoundError(SapConnectionError):
    """Raised when a requested SAP2000 major version cannot be found."""


class SapVersionMismatchError(SapConnectionError):
    """Raised when the connected SAP2000 process is not the requested version."""

    def __init__(self, requested: int, actual: int | None) -> None:
        self.requested = requested
        self.actual = actual
        super().__init__(f"Requested SAP2000 major version {requested}, got {actual}.")


class SapCompatibilityError(SapError):
    """Raised when a connected SAP2000 version has no compatibility entry."""


class MissingDependencyError(SapError):
    """Raised when an optional feature is used without its extra installed.

    Parameters
    ----------
    feature:
        Human-readable feature name, e.g. ``"DXF section import"``.
    extra:
        The pip extra that provides it, e.g. ``"sections"``.
    """

    def __init__(self, feature: str, extra: str) -> None:
        self.feature = feature
        self.extra = extra
        super().__init__(
            f"{feature} requires the optional '{extra}' dependencies. "
            f"Install them with: pip install 'sap2000py[{extra}]'"
        )


class SapComError(SapError):
    """Raised when a COM call itself fails (marshalling, dead process, ...).

    This wraps a :class:`comtypes.COMError` and preserves the originating
    OAPI path and the HRESULT for diagnosis.
    """

    def __init__(self, api_name: str, args: tuple[Any, ...], hresult: int | None = None) -> None:
        self.api_name = api_name
        self.args_passed = args
        self.hresult = hresult
        detail = f" (HRESULT={hresult:#010x})" if hresult is not None else ""
        super().__init__(f"COM call to '{api_name}' failed{detail}.")


class SapApiError(SapError):
    """Raised when an OAPI function returns a non-zero status code.

    The OAPI convention is that the last element of a call's return value is a
    ``Long`` status where ``0`` means success. :class:`~sap2000py.gateway.ComGateway`
    turns every non-zero status into this exception.
    """

    def __init__(self, api_name: str, args: tuple[Any, ...], code: int, hint: str = "") -> None:
        self.api_name = api_name
        self.args_passed = args
        self.code = code
        self.hint = hint
        message = f"OAPI call '{api_name}' returned non-zero status {code}. Arguments: {args!r}"
        if hint:
            message = f"{message}\n{hint}"
        super().__init__(message)


class SapNameNotFoundError(SapError):
    """Raised when a client-side name validation cannot find an object."""

    def __init__(
        self, name: str, *, kind: str = "object", available: list[str] | None = None
    ) -> None:
        self.name = name
        self.kind = kind
        self.available = available
        message = f"No {kind} named {name!r}."
        if available is not None:
            message = f"{message} Available names: {available!r}."
        super().__init__(message)


class SapAnalysisError(SapError):
    """Raised when one or more requested analysis cases fail to complete."""

    def __init__(self, failed: dict[str, str]) -> None:
        self.failed = failed
        joined = ", ".join(f"{name} ({status})" for name, status in failed.items())
        super().__init__(f"Analysis did not complete for: {joined}")
