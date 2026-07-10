"""Tests for SapClient teardown semantics (no real COM needed).

These build a :class:`SapClient` directly over a tiny fake ``cOAPI`` object.
Construction is COM-free (``comtypes`` is only imported in ``launch``/``attach``),
so the lifecycle logic is unit-testable anywhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sap2000py.client as client_module
from sap2000py.client import SapClient
from sap2000py.discovery import Installation
from sap2000py.errors import (
    SapApiError,
    SapConnectionError,
    SapGatewayClosedError,
    SapVersionMismatchError,
    SapVersionNotFoundError,
)


class FakeSapObject:
    """Minimal stand-in for the comtypes ``cOAPI`` application object.

    ``ApplicationExit`` returns the next status in ``exit_statuses`` (OAPI
    convention: 0 == success, non-zero == failure) and counts its calls.
    """

    def __init__(self, exit_statuses: list[int], *, version: str = "25.0.0") -> None:
        self.SapModel = FakeSapModel(version)
        self._exit_statuses = exit_statuses
        self.exit_calls = 0
        self.start_calls: list[tuple[int, bool, str]] = []

    def ApplicationStart(self, units: int, visible: bool, file_name: str) -> int:
        self.start_calls.append((units, visible, file_name))
        return 0

    def ApplicationExit(self, _save: bool) -> int:
        self.exit_calls += 1
        return self._exit_statuses.pop(0)


class FakeSapModel:
    def __init__(self, version: str) -> None:
        self.version = version
        self.new_blank_calls = 0

    def GetVersion(self, _version: str, _number: float):
        return self.version, float(self.version.split(".")[0]), 0

    def InitializeNewModel(self, _units: int) -> int:
        self.new_blank_calls += 1
        return 0


class FakeHelper:
    def __init__(self, obj: FakeSapObject) -> None:
        self.obj = obj
        self.created_paths: list[str] = []
        self.created_progids: list[str] = []
        self.attached_progids: list[str] = []

    def CreateObject(self, path: str) -> FakeSapObject:
        self.created_paths.append(path)
        return self.obj

    def CreateObjectProgID(self, progid: str) -> FakeSapObject:
        self.created_progids.append(progid)
        return self.obj

    def GetObject(self, progid: str) -> FakeSapObject:
        self.attached_progids.append(progid)
        return self.obj


def make_client(exit_statuses: list[int], *, owns_process: bool = True) -> SapClient:
    return SapClient(FakeSapObject(exit_statuses), owns_process=owns_process)


def test_attach_uses_running_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = FakeSapObject([0])
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    client = SapClient.attach()

    assert client.raw_object is obj
    assert helper.attached_progids == ["CSI.SAP2000.API.SapObject"]


def test_attach_does_not_accept_an_error_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = FakeSapObject([0])
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    with pytest.raises(TypeError, match="policy"):
        SapClient.attach(policy="warn")  # type: ignore[call-arg]


def test_attach_or_launch_does_not_accept_an_error_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attached = make_client([0], owns_process=False)

    def fake_attach(cls):
        return attached

    monkeypatch.setattr(SapClient, "attach", classmethod(fake_attach))

    with pytest.raises(TypeError, match="policy"):
        SapClient.attach_or_launch(policy="warn")


def test_attach_or_launch_rejects_misspelled_launch_keyword() -> None:
    with pytest.raises(TypeError, match="visble"):
        SapClient.attach_or_launch(visble=False)  # type: ignore[call-arg]


def test_attach_raises_when_no_running_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    class MissingHelper:
        def GetObject(self, _progid: str) -> None:
            raise OSError("not running")

    monkeypatch.setattr(client_module, "_make_helper", MissingHelper)

    with pytest.raises(SapConnectionError, match="No running SAP2000 instance"):
        SapClient.attach()


def test_attach_wraps_com_error_when_no_running_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingHelper:
        def GetObject(self, _progid: str) -> None:
            raise client_module.COMError(-1, "not running", None)

    monkeypatch.setattr(client_module, "_make_helper", MissingHelper)

    with pytest.raises(SapConnectionError, match="No running SAP2000 instance"):
        SapClient.attach()


def test_installations_delegates_to_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    discovered = [Installation(version="25.1.0", major=25, path=Path("C:/SAP25/SAP2000.exe"))]
    monkeypatch.setattr(client_module, "installations", lambda: discovered)

    assert SapClient.installations() is discovered


def test_raw_model_returns_underlying_sap_model() -> None:
    obj = FakeSapObject([0])
    client = SapClient(obj, owns_process=False)

    assert client.raw_model is obj.SapModel


def test_close_exits_owned_process_once() -> None:
    client = make_client([0])
    client.close()
    assert client._object.exit_calls == 1
    # Second close is a no-op once the process is known gone.
    client.close()
    assert client._object.exit_calls == 1


def test_failed_exit_raises_and_stays_retryable() -> None:
    # First ApplicationExit fails (status 1), second succeeds.
    client = make_client([1, 0])
    with pytest.raises(SapApiError):
        client.close()
    assert client._object.exit_calls == 1
    # Not marked closed: a retry must actually re-attempt the exit.
    client.close()
    assert client._object.exit_calls == 2


def test_failed_save_leaves_client_open_for_close_retry() -> None:
    client = make_client([0])

    class File:
        def Save(self, _path: str) -> int:
            return 1

    client.raw_model.File = File()

    with pytest.raises(SapApiError, match=r"File\.Save"):
        client.close(save="model.sdb")

    assert client._closed is False
    assert client._object.exit_calls == 0

    client.close()
    assert client._object.exit_calls == 1


def test_close_closes_the_gateway_after_owned_process_exit() -> None:
    client = make_client([0])
    gw = client._gateway

    client.close()

    with pytest.raises(SapGatewayClosedError, match="gateway is closed"):
        gw.call(lambda: 0, api_name="File.Save")


def test_closed_client_rejects_typed_and_native_facade_access() -> None:
    client = make_client([0])
    raw_model = client.raw_model
    raw_object = client.raw_object
    client.close()

    with pytest.raises(SapGatewayClosedError, match="gateway is closed"):
        client.model.files.save()
    with pytest.raises(SapGatewayClosedError, match="gateway is closed"):
        _ = client.api.File

    assert client.raw_model is raw_model
    assert client.raw_object is raw_object


def test_attached_instance_is_not_exited() -> None:
    client = make_client([0], owns_process=False)
    gw = client._gateway
    client.close()
    assert client._object.exit_calls == 0
    assert client._closed is True
    with pytest.raises(SapGatewayClosedError, match="gateway is closed"):
        gw.call(lambda: 0, api_name="File.Save")


def test_context_manager_exits_owned_process() -> None:
    obj = FakeSapObject([0])
    with SapClient(obj, owns_process=True):
        pass
    assert obj.exit_calls == 1


def test_context_exit_does_not_mask_body_exception() -> None:
    # ApplicationExit fails, but a body exception must propagate unmasked.
    obj = FakeSapObject([1])
    with pytest.raises(ValueError, match="boom"), SapClient(obj, owns_process=True):
        raise ValueError("boom")
    assert obj.exit_calls == 1


def test_context_exit_surfaces_teardown_failure_when_body_clean() -> None:
    # No body exception: a failed teardown is surfaced, not swallowed.
    obj = FakeSapObject([1])
    with pytest.raises(SapApiError), SapClient(obj, owns_process=True):
        pass
    assert obj.exit_calls == 1


def test_launch_version_and_program_path_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="version and program_path"):
        SapClient.launch(version="25", program_path="C:/SAP2000.exe")


def test_launch_wraps_com_error_for_bad_program_path(monkeypatch: pytest.MonkeyPatch) -> None:
    class MissingHelper:
        def CreateObject(self, _path: str) -> None:
            raise client_module.COMError(-1, "missing executable", None)

    monkeypatch.setattr(client_module, "_make_helper", MissingHelper)

    with pytest.raises(SapConnectionError, match="Cannot start a new SAP2000 instance"):
        SapClient.launch(program_path="Z:/missing/SAP2000.exe")


def test_launch_version_not_found_lists_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client_module,
        "installations",
        lambda: [Installation(version="24.0.0", major=24, path=Path("C:/SAP24/SAP2000.exe"))],
    )
    with pytest.raises(SapVersionNotFoundError, match="25"):
        SapClient.launch(version="25")


def test_launch_version_selects_highest_known_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = FakeSapObject([0], version="25.1.0")
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)
    monkeypatch.setattr(
        client_module,
        "installations",
        lambda: [
            Installation(version="25.0.0", major=25, path=Path("C:/SAP25/SAP2000.exe")),
            Installation(version="25.1.0", major=25, path=Path("C:/SAP251/SAP2000.exe")),
        ],
    )

    client = SapClient.launch(version="25", new_model=False)

    assert helper.created_paths == [str(Path("C:/SAP251/SAP2000.exe"))]
    assert obj.start_calls
    assert client.version == "25.1.0"


def test_launch_version_ambiguous_highest_patch_requires_program_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client_module,
        "installations",
        lambda: [
            Installation(version="25.1.0", major=25, path=Path("C:/SAP251A/SAP2000.exe")),
            Installation(version="25.1.0", major=25, path=Path("C:/SAP251B/SAP2000.exe")),
        ],
    )

    with pytest.raises(SapVersionNotFoundError, match="program_path"):
        SapClient.launch(version="25", new_model=False)


def test_launch_version_mismatch_exits_before_new_model(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = FakeSapObject([0], version="26.0.0")
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)
    monkeypatch.setattr(
        client_module,
        "installations",
        lambda: [Installation(version="25.0.0", major=25, path=Path("C:/SAP25/SAP2000.exe"))],
    )

    with pytest.raises(SapVersionMismatchError):
        SapClient.launch(version="25", new_model=True)

    assert obj.exit_calls == 1
    assert obj.SapModel.new_blank_calls == 0


def test_launch_exits_process_when_application_start_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obj = FakeSapObject([0])
    obj.ApplicationStart = lambda units, visible, file_name: 7
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    with pytest.raises(SapApiError, match="ApplicationStart"):
        SapClient.launch(new_model=False)

    assert obj.exit_calls == 1


def test_launch_exits_process_when_client_construction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    obj = FakeSapObject([0])
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    def fail_construction(self, *args, **kwargs) -> None:
        raise RuntimeError("construction failed")

    monkeypatch.setattr(SapClient, "__init__", fail_construction)

    with pytest.raises(RuntimeError, match="construction failed"):
        SapClient.launch(new_model=False)

    assert obj.exit_calls == 1


def test_launch_exits_process_on_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = FakeSapObject([0])

    def interrupt_start(_units: int, _visible: bool, _file_name: str) -> int:
        raise KeyboardInterrupt

    obj.ApplicationStart = interrupt_start
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    with pytest.raises(KeyboardInterrupt):
        SapClient.launch(new_model=False)

    assert obj.exit_calls == 1


def test_launch_does_not_mask_launch_failure_when_cleanup_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ApplicationExit cleanup itself fails (status 1); the original
    # ApplicationStart failure must still be what propagates.
    obj = FakeSapObject([1])
    obj.ApplicationStart = lambda units, visible, file_name: 7
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    with pytest.raises(SapApiError, match="ApplicationStart"):
        SapClient.launch(new_model=False)

    assert obj.exit_calls == 1


def test_launch_exits_process_when_new_blank_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = FakeSapObject([0])
    obj.SapModel.InitializeNewModel = lambda units: 7
    helper = FakeHelper(obj)
    monkeypatch.setattr(client_module, "_make_helper", lambda: helper)

    with pytest.raises(SapApiError, match="InitializeNewModel"):
        SapClient.launch(new_model=True)

    assert obj.exit_calls == 1


def test_attach_or_launch_reuses_matching_running_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attached = SapClient(FakeSapObject([0], version="25.0.0"), owns_process=False)
    launched = SapClient(FakeSapObject([0], version="25.0.0"), owns_process=True)
    launch_calls: list[dict[str, object]] = []

    def fake_attach(cls):
        return attached

    def fake_launch(cls, **kwargs):
        launch_calls.append(kwargs)
        return launched

    monkeypatch.setattr(SapClient, "attach", classmethod(fake_attach))
    monkeypatch.setattr(SapClient, "launch", classmethod(fake_launch))

    client = SapClient.attach_or_launch(version="25", visible=False)

    assert client is attached
    assert launch_calls == []


def test_attach_or_launch_rejects_version_and_program_path_before_attach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attached = SapClient(FakeSapObject([0], version="25.0.0"), owns_process=False)
    attach_calls = 0
    launch_calls: list[dict[str, object]] = []

    def fake_attach(cls):
        nonlocal attach_calls
        attach_calls += 1
        return attached

    def fake_launch(cls, **kwargs):
        launch_calls.append(kwargs)
        return attached

    monkeypatch.setattr(SapClient, "attach", classmethod(fake_attach))
    monkeypatch.setattr(SapClient, "launch", classmethod(fake_launch))

    with pytest.raises(ValueError, match="version and program_path"):
        SapClient.attach_or_launch(version="25", program_path="C:/SAP2000.exe")

    assert attach_calls == 0
    assert launch_calls == []


def test_attach_or_launch_raises_on_mismatched_running_version_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attached = SapClient(FakeSapObject([0], version="24.0.0"), owns_process=False)
    launched = SapClient(FakeSapObject([0], version="25.0.0"), owns_process=True)
    launch_calls: list[dict[str, object]] = []

    def fake_attach(cls):
        return attached

    def fake_launch(cls, **kwargs):
        launch_calls.append(kwargs)
        return launched

    monkeypatch.setattr(SapClient, "attach", classmethod(fake_attach))
    monkeypatch.setattr(SapClient, "launch", classmethod(fake_launch))

    with pytest.raises(SapVersionMismatchError):
        SapClient.attach_or_launch(version="25", visible=False)

    assert launch_calls == []
    assert attached.raw_object.exit_calls == 0


def test_attach_or_launch_can_launch_on_mismatched_running_version_when_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attached = SapClient(FakeSapObject([0], version="24.0.0"), owns_process=False)
    launched = SapClient(FakeSapObject([0], version="25.0.0"), owns_process=True)
    launch_calls: list[dict[str, object]] = []

    def fake_attach(cls):
        return attached

    def fake_launch(cls, **kwargs):
        launch_calls.append(kwargs)
        return launched

    monkeypatch.setattr(SapClient, "attach", classmethod(fake_attach))
    monkeypatch.setattr(SapClient, "launch", classmethod(fake_launch))

    client = SapClient.attach_or_launch(
        version="25",
        visible=False,
        launch_on_version_mismatch=True,
    )

    assert client is launched
    assert launch_calls == [
        {
            "visible": False,
            "version": "25",
            "program_path": None,
            "new_model": True,
            "units": client_module.Units.KN_M_C,
        }
    ]
    assert attached.raw_object.exit_calls == 0
