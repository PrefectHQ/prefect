"""Tests for the docket worker supervisor in background_workers.py."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Callable
from uuid import uuid4

import pytest
from docket import Docket

from prefect.server.api import background_workers
from prefect.server.api.background_workers import (
    _run_worker_with_reconnect,
    background_worker,
)
from prefect.settings import get_current_settings


@pytest.fixture
def docket_factory() -> Callable[[], Docket]:
    """Factory yielding fresh Dockets for the supervisor to rebuild on each attempt."""
    settings = get_current_settings()

    def _make() -> Docket:
        return Docket(
            name=f"test-docket-{uuid4().hex[:8]}",
            url=settings.server.docket.url,
            execution_ttl=timedelta(0),
        )

    return _make


def _patch_docket_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    base: float = 0.01,
    maximum: float = 0.05,
    max_attempts: int = 0,
) -> None:
    current = get_current_settings()
    new_docket = current.server.docket.model_copy(
        update={
            "worker_reconnect_base_delay_seconds": base,
            "worker_reconnect_max_delay_seconds": maximum,
            "worker_max_restart_attempts": max_attempts,
        }
    )
    new_server = current.server.model_copy(update={"docket": new_docket})
    new_settings = current.model_copy(update={"server": new_server})
    monkeypatch.setattr(
        background_workers, "get_current_settings", lambda: new_settings
    )


@pytest.fixture
def fast_reconnect_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_docket_settings(monkeypatch)


class _FakeWorker:
    """Drop-in replacement for docket.Worker whose run_forever is programmable."""

    instances: list["_FakeWorker"] = []

    def __init__(self, docket: Docket) -> None:
        self.docket = docket
        self.run_forever_calls = 0
        _FakeWorker.instances.append(self)

    async def __aenter__(self) -> "_FakeWorker":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def run_forever(self) -> None:
        self.run_forever_calls += 1
        behavior = _FakeWorker.behaviors.pop(0)
        await behavior(self)

    # Class-level scripted behaviors for each run_forever call, in order.
    behaviors: list[Any] = []


async def _never(_worker: _FakeWorker) -> None:
    """Block forever — used to simulate a healthy worker that is later cancelled."""
    await asyncio.Event().wait()


async def _raise_connection_error(_worker: _FakeWorker) -> None:
    import redis.exceptions

    raise redis.exceptions.ConnectionError("simulated redis outage")


async def _raise_unexpected(_worker: _FakeWorker) -> None:
    raise RuntimeError("simulated unexpected worker failure")


async def _return_early(_worker: _FakeWorker) -> None:
    # Simulate run_forever returning without an exception.
    return None


@pytest.fixture(autouse=True)
def reset_fake_worker() -> None:
    _FakeWorker.instances.clear()
    _FakeWorker.behaviors.clear()
    yield
    _FakeWorker.instances.clear()
    _FakeWorker.behaviors.clear()


@pytest.fixture
def patch_worker(monkeypatch: pytest.MonkeyPatch) -> type[_FakeWorker]:
    monkeypatch.setattr(background_workers, "Worker", _FakeWorker)
    return _FakeWorker


@pytest.fixture
def patch_register(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record calls to register_and_schedule_perpetual_services."""
    calls: list[dict[str, Any]] = []

    async def _record(docket: Docket, *, ephemeral: bool, webserver_only: bool) -> None:
        calls.append(
            {
                "docket_name": docket.name,
                "ephemeral": ephemeral,
                "webserver_only": webserver_only,
            }
        )

    monkeypatch.setattr(
        background_workers,
        "register_and_schedule_perpetual_services",
        _record,
    )
    return calls


@pytest.mark.timeout(10)
async def test_supervisor_rebuilds_worker_on_unexpected_exception(
    docket_factory: Callable[[], Docket],
    patch_worker: type[_FakeWorker],
    patch_register: list[dict[str, Any]],
    fast_reconnect_settings: None,
) -> None:
    # Fail once, then block healthily.
    _FakeWorker.behaviors = [_raise_unexpected, _never]

    shutdown = asyncio.Event()
    supervisor = asyncio.create_task(
        _run_worker_with_reconnect(
            docket_factory,
            ephemeral=False,
            webserver_only=False,
            shutdown_event=shutdown,
        )
    )

    # Wait until the second Worker is constructed and entered run_forever.
    for _ in range(500):
        if len(_FakeWorker.instances) >= 2 and _FakeWorker.instances[1].run_forever_calls == 1:
            break
        await asyncio.sleep(0.01)
    else:
        shutdown.set()
        supervisor.cancel()
        pytest.fail("supervisor never rebuilt the worker after failure")

    assert len(_FakeWorker.instances) == 2
    # Perpetuals were re-registered for each Worker instance.
    assert len(patch_register) == 2

    supervisor.cancel()
    try:
        await supervisor
    except asyncio.CancelledError:
        pass


@pytest.mark.timeout(10)
async def test_supervisor_rebuilds_on_connection_error(
    docket_factory: Callable[[], Docket],
    patch_worker: type[_FakeWorker],
    patch_register: list[dict[str, Any]],
    fast_reconnect_settings: None,
) -> None:
    _FakeWorker.behaviors = [_raise_connection_error, _never]

    shutdown = asyncio.Event()
    supervisor = asyncio.create_task(
        _run_worker_with_reconnect(
            docket_factory,
            ephemeral=False,
            webserver_only=False,
            shutdown_event=shutdown,
        )
    )

    for _ in range(500):
        if len(_FakeWorker.instances) >= 2:
            break
        await asyncio.sleep(0.01)

    assert len(_FakeWorker.instances) == 2
    supervisor.cancel()
    try:
        await supervisor
    except asyncio.CancelledError:
        pass


@pytest.mark.timeout(10)
async def test_supervisor_treats_clean_return_as_failure(
    docket_factory: Callable[[], Docket],
    patch_worker: type[_FakeWorker],
    patch_register: list[dict[str, Any]],
    fast_reconnect_settings: None,
) -> None:
    # run_forever returns cleanly the first time — we should still rebuild.
    _FakeWorker.behaviors = [_return_early, _never]

    shutdown = asyncio.Event()
    supervisor = asyncio.create_task(
        _run_worker_with_reconnect(
            docket_factory,
            ephemeral=False,
            webserver_only=False,
            shutdown_event=shutdown,
        )
    )

    for _ in range(500):
        if len(_FakeWorker.instances) >= 2:
            break
        await asyncio.sleep(0.01)

    assert len(_FakeWorker.instances) == 2
    supervisor.cancel()
    try:
        await supervisor
    except asyncio.CancelledError:
        pass


@pytest.mark.timeout(10)
async def test_supervisor_gives_up_after_max_attempts(
    docket_factory: Callable[[], Docket],
    patch_worker: type[_FakeWorker],
    patch_register: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_docket_settings(monkeypatch, base=0.01, maximum=0.02, max_attempts=2)

    _FakeWorker.behaviors = [
        _raise_unexpected,
        _raise_unexpected,
        _raise_unexpected,
    ]

    shutdown = asyncio.Event()
    with pytest.raises(RuntimeError, match="simulated unexpected"):
        await _run_worker_with_reconnect(
            docket_factory,
            ephemeral=False,
            webserver_only=False,
            shutdown_event=shutdown,
        )

    assert len(_FakeWorker.instances) == 3


@pytest.mark.timeout(10)
async def test_background_worker_cancels_supervisor_on_shutdown(
    docket_factory: Callable[[], Docket],
    patch_worker: type[_FakeWorker],
    patch_register: list[dict[str, Any]],
    fast_reconnect_settings: None,
) -> None:
    _FakeWorker.behaviors = [_never]

    async with background_worker(
        docket_factory, ephemeral=False, webserver_only=False
    ):
        # Give the supervisor a tick to construct the Worker.
        for _ in range(500):
            if _FakeWorker.instances and _FakeWorker.instances[0].run_forever_calls == 1:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("supervisor never started the worker")

    # After exit, no further workers should have been built.
    assert len(_FakeWorker.instances) == 1
