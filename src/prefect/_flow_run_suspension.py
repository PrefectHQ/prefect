from __future__ import annotations

import asyncio
import contextvars
import threading
from contextlib import contextmanager
from typing import Callable, Generator, NamedTuple
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


def _start_flow_run_suspension_observer(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
    polling_interval: float = 10,
) -> tuple[threading.Thread, threading.Event, threading.Event]:
    """
    Start a thread that watches a flow run for suspension.

    Returns the thread, an event that is set once the observer has made its first
    check of the flow run, and an event that stops the thread when set.
    """
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
    return thread, ready_event, stop_event


@contextmanager
def observe_flow_run_suspension(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
    polling_interval: float = 10,
) -> Generator[None, None, None]:
    thread, ready_event, stop_event = _start_flow_run_suspension_observer(
        flow_run_id, suspension_request, polling_interval
    )
    ready_event.wait()

    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=2)


class PrestartedFlowRunSuspensionObserver(NamedTuple):
    suspension_request: FlowRunSuspensionRequest
    ready_event: threading.Event


_prestarted_flow_run_suspension_observers: dict[
    UUID, PrestartedFlowRunSuspensionObserver
] = {}
_prestarted_flow_run_suspension_observers_lock = threading.Lock()


@contextmanager
def prestart_flow_run_suspension_observer(
    flow_run_id: UUID,
) -> Generator[Callable[[], None], None, None]:
    """
    Start watching a flow run for suspension without waiting for the first check,
    so the observer connects while the caller loads the flow run and the flow.

    The flow run engine for this flow run uses this observer, through
    `adopt_prestarted_flow_run_suspension_observer`, instead of starting its own.
    Calling the yielded function stops the observer early, and the engine then
    behaves as if no observer was prestarted.
    """
    suspension_request = FlowRunSuspensionRequest()
    thread, ready_event, stop_event = _start_flow_run_suspension_observer(
        flow_run_id, suspension_request
    )
    prestarted_observer = PrestartedFlowRunSuspensionObserver(
        suspension_request, ready_event
    )
    with _prestarted_flow_run_suspension_observers_lock:
        _prestarted_flow_run_suspension_observers[flow_run_id] = prestarted_observer

    def stop() -> None:
        with _prestarted_flow_run_suspension_observers_lock:
            if (
                _prestarted_flow_run_suspension_observers.get(flow_run_id)
                is prestarted_observer
            ):
                _prestarted_flow_run_suspension_observers.pop(flow_run_id, None)
        stop_event.set()

    try:
        yield stop
    finally:
        stopped_early = stop_event.is_set()
        stop()
        # The thread checks `stop_event` only after its first check of the flow
        # run. Joining a thread that has not made that check, or one stopped
        # early for a run without a deployment, would delay the caller.
        if not stopped_early and ready_event.is_set():
            thread.join(timeout=2)


def adopt_prestarted_flow_run_suspension_observer(
    flow_run_id: UUID,
) -> PrestartedFlowRunSuspensionObserver | None:
    """
    Return the observer prestarted for `flow_run_id`, or None if there is none.

    The caller must use the observer's `suspension_request` as its own, and wait
    for its `ready_event` before it proposes a Running state.
    """
    with _prestarted_flow_run_suspension_observers_lock:
        return _prestarted_flow_run_suspension_observers.get(flow_run_id)
