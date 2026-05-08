from __future__ import annotations

import asyncio
import contextvars
import threading
from contextlib import contextmanager
from typing import Generator
from uuid import UUID

from prefect.client.schemas.objects import State
from prefect.exceptions import Pause
from prefect.logging.loggers import get_logger


class FlowRunSuspensionSignal:
    """Mutable in-process signal shared by flow, child flow, and task contexts."""

    def __init__(self) -> None:
        self._state: State | None = None
        self._lock = threading.Lock()

    def set(self, state: State) -> None:
        with self._lock:
            self._state = state

    def get(self) -> State | None:
        with self._lock:
            return self._state

    def is_set(self) -> bool:
        return self.get() is not None

    def raise_if_suspended(self) -> None:
        if state := self.get():
            raise Pause(state=state)


_active_flow_run_suspension_signals: dict[UUID, FlowRunSuspensionSignal] = {}
_active_flow_run_suspension_signals_lock = threading.Lock()


@contextmanager
def register_flow_run_suspension_signal(
    flow_run_id: UUID,
    signal: FlowRunSuspensionSignal,
) -> Generator[None, None, None]:
    with _active_flow_run_suspension_signals_lock:
        _active_flow_run_suspension_signals[flow_run_id] = signal

    try:
        yield
    finally:
        with _active_flow_run_suspension_signals_lock:
            if _active_flow_run_suspension_signals.get(flow_run_id) is signal:
                _active_flow_run_suspension_signals.pop(flow_run_id, None)


def signal_flow_run_suspension(flow_run_id: UUID, state: State) -> bool:
    with _active_flow_run_suspension_signals_lock:
        signal = _active_flow_run_suspension_signals.get(flow_run_id)

    if signal is None:
        return False

    signal.set(state)
    return True


def raise_if_flow_run_suspension_requested() -> None:
    from prefect.context import FlowRunContext

    if flow_run_context := FlowRunContext.get():
        flow_run_context.flow_run_suspension_signal.raise_if_suspended()


@contextmanager
def observe_flow_run_suspension(
    flow_run_id: UUID,
    signal: FlowRunSuspensionSignal,
    polling_interval: float = 10,
) -> Generator[None, None, None]:
    from prefect._observers import FlowRunSuspendingObserver

    logger = get_logger("flow_run_suspension")
    stop_event = threading.Event()
    ready_event = threading.Event()

    def mark_suspended(observed_flow_run_id: UUID, state: State) -> None:
        if not signal_flow_run_suspension(observed_flow_run_id, state):
            signal.set(state)

    async def run_observer() -> None:
        async with FlowRunSuspendingObserver(
            on_suspended=mark_suspended,
            polling_interval=polling_interval,
        ) as observer:
            await observer.watch_flow_run_id(flow_run_id)
            ready_event.set()
            while not stop_event.is_set():
                await asyncio.sleep(0.2)

    context = contextvars.copy_context()

    def observer_thread() -> None:
        try:
            context.run(lambda: asyncio.run(run_observer()))
        except Exception:
            logger.debug(
                "Flow run suspension observer exited with an exception",
                exc_info=True,
            )
        finally:
            ready_event.set()

    thread = threading.Thread(target=observer_thread, daemon=True)
    thread.start()
    ready_event.wait(timeout=2)

    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=2)
