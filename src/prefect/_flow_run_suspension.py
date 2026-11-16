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
from prefect.settings import PREFECT_API_URL


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
) -> tuple[threading.Thread, threading.Event, Callable[[], None]]:
    """
    Start a thread that watches a flow run for suspension.

    Returns the thread, an event that is set once the observer has made its first
    check of the flow run or has exited, and a function that stops the thread.
    """
    from prefect._internal.observers import FlowRunSuspendingObserver

    logger = get_logger("flow_run_suspension")
    stop_event = threading.Event()
    ready_event = threading.Event()
    observer_task_lock = threading.Lock()
    observer_task: tuple[asyncio.AbstractEventLoop, asyncio.Task[None]] | None = None

    def mark_suspended(flow_run_id: UUID, state: State) -> None:
        if not mark_flow_run_suspension_requested(flow_run_id, state):
            suspension_request.mark_requested(state)

    async def watch_until_stopped() -> None:
        async with FlowRunSuspendingObserver(
            on_suspended=mark_suspended,
            polling_interval=polling_interval,
        ) as observer:
            await observer.watch_flow_run_id(flow_run_id)
            ready_event.set()
            while not stop_event.is_set():
                await asyncio.sleep(0.2)

    async def run_observer() -> None:
        nonlocal observer_task
        task = asyncio.current_task()
        with observer_task_lock:
            if stop_event.is_set() or task is None:
                return
            observer_task = (asyncio.get_running_loop(), task)
        try:
            await watch_until_stopped()
        except asyncio.CancelledError:
            if not stop_event.is_set():
                raise
        finally:
            with observer_task_lock:
                observer_task = None

    def stop() -> None:
        nonlocal observer_task
        with observer_task_lock:
            stop_event.set()
            if observer_task is None:
                return
            loop, task = observer_task
            observer_task = None

            # The first check retries until it reads the flow run and never polls
            # `stop_event`, so a thread still in it must be cancelled to exit.
            # Checking `ready_event` on the loop thread, where it is set, keeps a
            # check that has already finished from being cancelled during cleanup.
            def cancel_during_first_check() -> None:
                if not ready_event.is_set():
                    task.cancel()

            loop.call_soon_threadsafe(cancel_during_first_check)

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
    return thread, ready_event, stop


@contextmanager
def observe_flow_run_suspension(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
    polling_interval: float = 10,
) -> Generator[None, None, None]:
    thread, ready_event, stop = _start_flow_run_suspension_observer(
        flow_run_id, suspension_request, polling_interval
    )
    ready_event.wait()

    try:
        yield
    finally:
        stop()
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
    Start a thread that watches a flow run for suspension, and yield a function
    that stops it.

    While the context is open and the observer is not stopped,
    `adopt_prestarted_flow_run_suspension_observer` returns this observer, and the
    flow run engine for `flow_run_id` uses it instead of starting its own. After
    the yielded function is called, the engine starts its own observer as if none
    was prestarted. Exiting the context stops the observer. If no API URL is
    configured, no observer is started and the yielded function does nothing.
    """
    if not PREFECT_API_URL.value():
        # Without an API URL, `get_client` starts an ephemeral server, and that
        # startup is not safe to run from the observer thread and the caller at
        # the same time.
        yield lambda: None
        return

    suspension_request = FlowRunSuspensionRequest()
    # The observer does not wait for its first check here, so it connects while
    # the caller loads the flow run and the flow.
    thread, ready_event, stop_observer = _start_flow_run_suspension_observer(
        flow_run_id, suspension_request
    )
    prestarted_observer = PrestartedFlowRunSuspensionObserver(
        suspension_request, ready_event
    )
    with _prestarted_flow_run_suspension_observers_lock:
        _prestarted_flow_run_suspension_observers[flow_run_id] = prestarted_observer
    stopped = threading.Event()

    def stop() -> None:
        with _prestarted_flow_run_suspension_observers_lock:
            if (
                _prestarted_flow_run_suspension_observers.get(flow_run_id)
                is prestarted_observer
            ):
                _prestarted_flow_run_suspension_observers.pop(flow_run_id, None)
        stopped.set()
        stop_observer()

    try:
        yield stop
    finally:
        stopped_early = stopped.is_set()
        stop()
        # A thread cancelled during its first check, or stopped early for a run
        # without a deployment, can take time to close its client. Joining it
        # would delay the caller, and no engine uses it.
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
