"""A thin dynamic proxy over the raw OAPI.

``client.api`` is a :class:`NativeApi` wrapping the root ``cSapModel``. Attribute
access walks the COM object tree and every method call is routed through the
:class:`~sap2000py.gateway.ComGateway`, so the *entire* OAPI is available with
centralized error handling without hand-writing a wrapper per method::

    name = client.api.PointObj.AddCartesian(0.0, 0.0, 0.0)   # returns assigned name
    n    = client.api.PointObj.Count()                       # returns the count

This single class replaces the ~5,465-line ``SapObj.py`` passthrough layer.
IDE completion for it comes from a generated ``native.pyi`` stub (see
``_stubgen``); at runtime everything is resolved dynamically.
"""

from __future__ import annotations

from typing import Any

from .gateway import ComGateway

# Values that should be returned verbatim rather than wrapped as a sub-node.
_PASSTHROUGH = (int, float, bool, complex, str, bytes, type(None), tuple, list, dict)


class NativeApi:
    """Dynamic, error-checked proxy for a node in the OAPI object tree.

    Parameters
    ----------
    gateway:
        The shared call gateway.
    node:
        The COM object this proxy wraps (the root ``SapModel`` for the proxy
        returned by ``client.api``).
    path:
        Dotted path to this node, used to label calls in errors and logs.
    """

    __slots__ = ("_gateway", "_node", "_path")

    def __init__(self, gateway: ComGateway, node: Any, path: str = "") -> None:
        object.__setattr__(self, "_gateway", gateway)
        object.__setattr__(self, "_node", node)
        object.__setattr__(self, "_path", path)

    @property
    def node(self) -> Any:
        """The raw comtypes object this proxy wraps."""
        return self._node

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            # Avoid intercepting dunder / private probes (copy, pickle, IPython).
            raise AttributeError(name)

        self._gateway.ensure_open()
        attr = getattr(self._node, name)
        full = f"{self._path}.{name}" if self._path else name

        if callable(attr):

            def _call(*args: Any, _func: Any = attr, _name: str = full) -> Any:
                return self._gateway.auto(_func, *args, api_name=_name)

            _call.__name__ = name
            _call.__qualname__ = full
            return _call

        if isinstance(attr, _PASSTHROUGH):
            return attr

        # Anything else is assumed to be a COM sub-interface (PointObj, ...).
        return NativeApi(self._gateway, node=attr, path=full)

    def __repr__(self) -> str:
        return f"<NativeApi {self._path or 'SapModel'!r}>"
