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
knowledge, uses :meth:`ComGateway.auto`. It cannot read a method's intent, so it
classifies the bare-scalar return *structurally*:

* a sequence is unambiguous — check the trailing status, return the out-params;
* a bare **non-integer** (``str``/``float``/``None`` — and ``bool``, which the
  OAPI never uses for a status) can't be a status, so it passes through;
* a bare **integer** is treated as an action status (raise on non-zero) *unless*
  its leaf name is in :data:`_VALUE_GETTERS`, a curated set of the only OAPI
  methods whose bare-``long`` return is a value rather than a status.

This defaults to the *safe* direction: a failed mutation through the escape hatch
(``client.api.File.Save(...)``) raises instead of being silently dropped. The set
was enumerated against the real SAP2000 type library — every other bare-``long``
return is an action status — so a value-getter wrongly treated as a status is
both rare and *loud* (it raises with a hint to use ``client.raw_model``), never a
silent wrong value.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from .errors import SapApiError, SapComError, SapGatewayClosedError

__all__ = ["COMError", "ComGateway"]

try:  # comtypes is Windows-only; keep the module importable elsewhere.
    from comtypes import COMError
except ImportError:  # pragma: no cover - exercised only off-Windows

    class COMError(Exception):  # type: ignore[no-redef]
        """Fallback so non-Windows imports don't fail; never raised by COM."""

        hresult: int | None = None


#: Leaf method names whose bare-``long`` comtypes return is a direct *value*, not
#: a status code — every other bare-``long`` return is an action status. Keyed by
#: leaf name only, which is collision-free (no interface reuses these names for a
#: status method). :meth:`ComGateway.auto` consults this set so the dynamic proxy
#: doesn't misread e.g. ``PointObj.Count() == 5`` as "failed status 5". A name not
#: in the set defaults to *status* (the loud, safe direction): a missing value
#: getter raises with a hint, never returns a silently-wrong value. The
#: ``Count*`` names were confirmed against the live OAPI by
#: ``sap2000py._stubgen.audit_value_getters``, which flags any new ones on a
#: SAP2000 upgrade so this set stays complete.
_VALUE_GETTERS = frozenset(
    {
        "Count",
        "CountCase",
        "CountConstraint",
        "CountLoadDispl",
        "CountLoadForce",
        "CountPanelZone",
        "CountPoint",
        "CountRestraint",
        "CountSpring",
        "GetDatabaseUnits",
        "GetPresentUnits",
    }
)


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
    """

    def __init__(self, sap_model: Any) -> None:
        self._model = sap_model
        self._closed = False

    @property
    def model(self) -> Any:
        """The raw comtypes ``SapModel`` escape hatch, unaffected by :meth:`close`."""
        return self._model

    def ensure_open(self) -> None:
        """Raise if this gateway has been closed."""
        if self._closed:
            raise SapGatewayClosedError()

    @property
    def checked_model(self) -> Any:
        """Return the model after enforcing this gateway's lifecycle."""
        self.ensure_open()
        return self._model

    def close(self) -> None:
        """Prevent this gateway from invoking the OAPI again."""
        self._closed = True

    # -- invocation ---------------------------------------------------------

    def _invoke(self, com_func: Callable[..., Any], args: tuple[Any, ...], api_name: str) -> Any:
        self.ensure_open()
        logger.trace("OAPI call {} args={!r}", api_name or getattr(com_func, "__name__", "?"), args)
        try:
            return com_func(*args)
        except COMError as exc:  # pragma: no cover - needs a live COM server
            hresult = getattr(exc, "hresult", None)
            raise SapComError(api_name, args, hresult=hresult) from exc

    def _check(self, code: int, api_name: str, args: tuple[Any, ...], hint: str = "") -> None:
        if code == 0:
            return
        raise SapApiError(api_name, args, code, hint=hint)

    # -- public call styles -------------------------------------------------

    def call(self, com_func: Callable[..., Any], *args: Any, api_name: str = "") -> Any:
        """Invoke a status-returning OAPI method and check the status.

        Returns the unpacked out-parameters: ``None`` if there were none, the
        single value if there was one, otherwise a tuple. Raises
        :class:`~sap2000py.errors.SapApiError` on a non-zero status.
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
        """Call for the dynamic proxy, classifying the return structurally.

        * Sequence result — check the trailing status, return the out-params.
        * Bare non-integer (``str``/``float``/``None``/``bool``) — a value;
          returned unchanged (the OAPI never encodes a status this way).
        * Bare integer — an action status by default: checked (raising on
          non-zero) and returned so raw-OAPI ``if ret != 0`` guards stay valid.
          The exception is a leaf name in :data:`_VALUE_GETTERS`, whose bare
          integer is a real value and is returned unchecked.

        Defaulting a bare integer to *status* is what stops a failed mutation
        through ``client.api`` (``File.Save``, ``RunAnalysis``, ...) from being
        silently dropped.
        """
        result = self._invoke(com_func, args, api_name)
        if isinstance(result, (list, tuple)):
            outs, code = _split_status(result)
            self._check(code, api_name, args)
            return _unpack(outs)
        # A status is always an integer; bool/str/float/None never are.
        if isinstance(result, bool) or not isinstance(result, int):
            return result
        leaf = api_name.rsplit(".", 1)[-1]
        if leaf in _VALUE_GETTERS:
            return result
        hint = (
            f"If '{api_name}' returns a value rather than a status, call it via "
            "client.raw_model (the unchecked escape hatch) and report it so its "
            "name can be added to the gateway's value-getter set."
        )
        self._check(result, api_name, args, hint=hint)
        return result
