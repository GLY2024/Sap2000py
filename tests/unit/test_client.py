"""Tests for SapClient teardown semantics (no real COM needed).

These build a :class:`SapClient` directly over a tiny fake ``cOAPI`` object.
Construction is COM-free (``comtypes`` is only imported in ``launch``/``attach``),
so the lifecycle logic is unit-testable anywhere.
"""

from __future__ import annotations

import pytest

from sap2000py.client import SapClient
from sap2000py.errors import SapApiError


class FakeSapObject:
    """Minimal stand-in for the comtypes ``cOAPI`` application object.

    ``ApplicationExit`` returns the next status in ``exit_statuses`` (OAPI
    convention: 0 == success, non-zero == failure) and counts its calls.
    """

    def __init__(self, exit_statuses: list[int]) -> None:
        self.SapModel = object()
        self._exit_statuses = exit_statuses
        self.exit_calls = 0

    def ApplicationExit(self, _save: bool) -> int:
        self.exit_calls += 1
        return self._exit_statuses.pop(0)


def make_client(exit_statuses: list[int], *, owns_process: bool = True) -> SapClient:
    return SapClient(FakeSapObject(exit_statuses), owns_process=owns_process)


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


def test_attached_instance_is_not_exited() -> None:
    client = make_client([0], owns_process=False)
    client.close()
    assert client._object.exit_calls == 0


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
