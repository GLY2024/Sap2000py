"""Shared pytest fixtures and the ``--sap`` integration gate.

Unit tests run anywhere: they drive the real :class:`ComGateway` over a
configurable fake COM object tree (:class:`FakeCom`), so they verify that the
typed managers call the right OAPI methods with the right arguments and unpack
results correctly — without a SAP2000 install.

Integration tests are marked ``@pytest.mark.sap`` and are skipped unless
``pytest --sap`` is passed (they need a real local SAP2000).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from sap2000py import SapClient, Units, installations
from sap2000py.gateway import ComGateway
from sap2000py.model import Model


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sap",
        action="store_true",
        default=False,
        help="run integration tests that require a real local SAP2000 install",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--sap"):
        return
    skip_sap = pytest.mark.skip(reason="needs a real SAP2000 install; run with --sap")
    for item in items:
        if "sap" in item.keywords:
            item.add_marker(skip_sap)


@pytest.fixture(scope="session")
def client(request: pytest.FixtureRequest) -> Iterator[SapClient]:
    """One owned SAP2000 process shared by all ``--sap`` integration tests."""
    if not request.config.getoption("--sap"):
        pytest.skip("needs a real SAP2000 install; run with --sap")
    available = [item for item in installations() if item.major is not None]
    if not available:
        pytest.skip("no discoverable SAP2000 installation")

    c = SapClient.launch(version=str(available[0].major), visible=False, units=Units.KN_M_C)
    try:
        yield c
    finally:
        c.close()


class FakeCom:
    """A configurable stand-in for a comtypes COM node tree.

    Attribute access walks a dotted path. A path present in ``responses`` is a
    *method*: calling it records ``(path, args)`` and returns the configured
    value (or the result of calling it with the args). Any other attribute is a
    sub-node. This lets a test wire up exactly the OAPI surface it exercises.
    """

    def __init__(
        self,
        responses: dict[str, Any],
        calls: list[tuple[str, tuple[Any, ...]]],
        path: str = "",
    ) -> None:
        object.__setattr__(self, "_responses", responses)
        object.__setattr__(self, "_calls", calls)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        full = f"{self._path}.{name}" if self._path else name
        if full in self._responses:
            resp = self._responses[full]

            def _method(*args: Any) -> Any:
                self._calls.append((full, args))
                return resp(*args) if callable(resp) else resp

            return _method
        return FakeCom(self._responses, self._calls, full)


@dataclass
class FakeHarness:
    """A :class:`Model` backed by a :class:`FakeCom`, plus the recorded calls."""

    model: Model
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def called(self, path: str) -> list[tuple[Any, ...]]:
        """All argument tuples recorded for ``path``."""
        return [args for name, args in self.calls if name == path]


@pytest.fixture
def make_model() -> Callable[[dict[str, Any]], FakeHarness]:
    """Factory: build a fake-backed Model from a ``{method_path: response}`` map."""

    def _make(responses: dict[str, Any] | None = None) -> FakeHarness:
        calls: list[tuple[str, tuple[Any, ...]]] = []
        fake = FakeCom(responses or {}, calls)
        gateway = ComGateway(fake)
        return FakeHarness(model=Model(gateway), calls=calls)

    return _make


@pytest.fixture
def make_proxy() -> Callable[[dict[str, Any]], tuple[Any, list[tuple[str, tuple[Any, ...]]]]]:
    """Factory: build a NativeApi over a fake COM tree, plus the recorded calls."""
    from sap2000py.native import NativeApi

    def _make(responses: dict[str, Any] | None = None):
        calls: list[tuple[str, tuple[Any, ...]]] = []
        fake = FakeCom(responses or {}, calls)
        return NativeApi(ComGateway(fake), node=fake), calls

    return _make
