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


class FlowRunSuspensionRequest:
    """
    Mutable in-process suspension request shared by flow, child flow, and task contexts.

    The stored state is the server-accepted `Suspended` state that should be raised
    through Prefect's existing `Pause` control-flow path at the next orchestration
    boundary.
    """

    def __init__(self) -> None:
        self._suspended_state: State | None = None
        self._lock = threading.Lock()

    def mark_requested(self, state: State) -> None:
        with self._lock:
            self._suspended_state = state

    def get_state(self) -> State | None:
        with self._lock:
            return self._suspended_state

    def is_requested(self) -> bool:
        return self.get_state() is not None

    def raise_if_requested(self) -> None:
        if state := self.get_state():
            raise Pause(state=state)


def is_suspended_flow_run_state(state: State | None) -> bool:
    return bool(state and state.is_paused() and state.name == "Suspended")


_active_flow_run_suspension_requests: dict[UUID, FlowRunSuspensionRequest] = {}
_active_flow_run_suspension_requests_lock = threading.Lock()


@contextmanager
def register_flow_run_suspension_request(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
) -> Generator[None, None, None]:
    with _active_flow_run_suspension_requests_lock:
        _active_flow_run_suspension_requests[flow_run_id] = suspension_request

    try:
        yield
    finally:
        with _active_flow_run_suspension_requests_lock:
            if (
                _active_flow_run_suspension_requests.get(flow_run_id)
                is suspension_request
            ):
                _active_flow_run_suspension_requests.pop(flow_run_id, None)


def mark_flow_run_suspension_requested(flow_run_id: UUID, state: State) -> bool:
    with _active_flow_run_suspension_requests_lock:
        suspension_request = _active_flow_run_suspension_requests.get(flow_run_id)

    if suspension_request is None:
        return False

    suspension_request.mark_requested(state)
    return True


def raise_if_flow_run_suspension_requested() -> None:
    from prefect.context import FlowRunContext

    if flow_run_context := FlowRunContext.get():
        flow_run_context.flow_run_suspension_request.raise_if_requested()


@contextmanager
def observe_flow_run_suspension(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
    polling_interval: float = 10,
) -> Generator[None, None, None]:
    from prefect._internal.observers import FlowRunSuspendingObserver

    logger = get_logger("flow_run_suspension")
    stop_event = threading.Event()
    ready_event = threading.Event()

    def mark_suspended(flow_run_id: UUID, state: State) -> None:
        if not mark_flow_run_suspension_requested(flow_run_id, state):
            suspension_request.mark_requested(state)

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
    ready_event.wait()

    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=2)
