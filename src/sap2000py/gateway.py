"""The single chokepoint for every OAPI call.

Why this exists
---------------
The old code scattered raw ``self._Model.X.Y(...)`` calls across ~9,000 lines
and checked the return code inconsistently (about a third of the time not at
all). :class:`ComGateway` makes every call go through one place that:

1. invokes the COM method and wraps any :class:`comtypes.COMError`;
2. unpacks comtypes' by-ref out-parameters;
3. checks the OAPI status code and raises :class:`~sap2000py.errors.SapApiError`.

The unpacking rule
------------------
Every OAPI function returns a ``long`` status as its *last* value, with any
``[out]`` parameters before it. comtypes therefore returns either:

* a bare scalar — when the function has no out-params (the scalar is *either*
  the status, *or*, for a handful of functions like ``Count()`` and
  ``GetPresentUnits()``, a direct value with no status at all); or
* a sequence ``(out_1, ..., out_n, status)`` — in which case the **last element
  is always the status** (this is unambiguous).

  comtypes returns this sequence as a **list** for methods with ``[in, out]``
  parameters (it routes them through its ``_fix_inout_args`` wrapper) and as a
  **tuple** for methods with only pure ``[out]`` parameters. The gateway treats
  both identically — a real-machine difference that unit tests with a fake COM
  cannot surface, caught by the integration smoke test.

Because a bare scalar is ambiguous, the typed ``model`` layer picks the right
method explicitly:

* :meth:`ComGateway.call`  — status semantics; raises on non-zero.
* :meth:`ComGateway.value` — direct-value semantics; never interprets a status.

The dynamic :class:`~sap2000py.native.NativeApi` proxy, which has no per-method
knowledge, uses :meth:`ComGateway.auto`: check+unpack tuples, return bare
scalars as-is (the safe default — never misread a real value as a failure).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from loguru import logger

from .errors import SapApiError, SapComError

try:  # comtypes is Windows-only; keep the module importable elsewhere.
    from comtypes import COMError
except ImportError:  # pragma: no cover - exercised only off-Windows

    class COMError(Exception):  # type: ignore[no-redef]
        """Fallback so non-Windows imports don't fail; never raised by COM."""

        hresult: int | None = None


class ErrorPolicy(Enum):
    """What the gateway does when an OAPI call returns a non-zero status."""

    RAISE = "raise"
    WARN = "warn"


def _split_status(result: list[Any] | tuple[Any, ...]) -> tuple[tuple[Any, ...], int]:
    """Split a comtypes sequence return into ``(out_params, status)``."""
    *outs, code = result
    return tuple(outs), int(code)


def _unpack(outs: tuple[Any, ...]) -> Any:
    """Collapse out-parameters to the friendliest Python value."""
    if not outs:
        return None
    if len(outs) == 1:
        return outs[0]
    return outs


class ComGateway:
    """Wraps a SAP2000 ``cSapModel`` and mediates every call to it.

    Parameters
    ----------
    sap_model:
        The raw comtypes ``SapModel`` object.
    policy:
        Behaviour on a non-zero status; defaults to
        :attr:`ErrorPolicy.RAISE`.
    """

    def __init__(self, sap_model: Any, policy: ErrorPolicy = ErrorPolicy.RAISE) -> None:
        self._model = sap_model
        self.policy = policy

    @property
    def model(self) -> Any:
        """The raw comtypes ``SapModel`` — the ultimate escape hatch."""
        return self._model

    # -- invocation ---------------------------------------------------------

    def _invoke(self, com_func: Callable[..., Any], args: tuple[Any, ...], api_name: str) -> Any:
        logger.trace("OAPI call {} args={!r}", api_name or getattr(com_func, "__name__", "?"), args)
        try:
            return com_func(*args)
        except COMError as exc:  # pragma: no cover - needs a live COM server
            hresult = getattr(exc, "hresult", None)
            raise SapComError(api_name, args, hresult=hresult) from exc

    def _check(self, code: int, api_name: str, args: tuple[Any, ...]) -> None:
        if code == 0:
            return
        error = SapApiError(api_name, args, code)
        if self.policy is ErrorPolicy.RAISE:
            raise error
        logger.warning("{}", error)

    # -- public call styles -------------------------------------------------

    def call(self, com_func: Callable[..., Any], *args: Any, api_name: str = "") -> Any:
        """Invoke a status-returning OAPI method and check the status.

        Returns the unpacked out-parameters: ``None`` if there were none, the
        single value if there was one, otherwise a tuple. Raises
        :class:`~sap2000py.errors.SapApiError` on a non-zero status (unless the
        policy is :attr:`ErrorPolicy.WARN`).
        """
        result = self._invoke(com_func, args, api_name)
        if isinstance(result, (list, tuple)):
            outs, code = _split_status(result)
            self._check(code, api_name, args)
            return _unpack(outs)
        # Bare scalar: the typed layer only routes genuine status returns here.
        self._check(int(result), api_name, args)
        return None

    def value(self, com_func: Callable[..., Any], *args: Any, api_name: str = "") -> Any:
        """Invoke a direct-value OAPI method (e.g. ``Count``, ``GetPresentUnits``).

        Returns the value as-is and never interprets it as a status. If the
        method also has out-parameters, the trailing status is still checked
        and the out-parameters are returned.
        """
        result = self._invoke(com_func, args, api_name)
        if isinstance(result, (list, tuple)):
            outs, code = _split_status(result)
            self._check(code, api_name, args)
            return _unpack(outs)
        return result

    def auto(self, com_func: Callable[..., Any], *args: Any, api_name: str = "") -> Any:
        """Best-effort call for the dynamic proxy with no per-method knowledge.

        Tuple result: check the trailing status and return the out-parameters.
        Bare scalar: return it unchanged (could be a status *or* a value; we
        never misread a real value as a failure).
        """
        result = self._invoke(com_func, args, api_name)
        if isinstance(result, (list, tuple)):
            outs, code = _split_status(result)
            self._check(code, api_name, args)
            return _unpack(outs)
        return result
