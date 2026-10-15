from __future__ import annotations

import asyncio
import contextvars
import threading
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from typing import AsyncGenerator, Callable, Generator
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


class _FlowRunSuspensionObserverThread:
    """
    Runs a `FlowRunSuspendingObserver` for one flow run on a dedicated thread.

    The observer gets its own thread and event loop so that it keeps receiving
    suspension events while flow code holds the caller's thread, for example
    when an async flow calls sync tasks.
    """

    def __init__(
        self,
        flow_run_id: UUID,
        suspension_request: FlowRunSuspensionRequest,
        polling_interval: float,
        on_ready: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        """
        Args:
            flow_run_id: The flow run to observe.
            suspension_request: The request to mark when the flow run is suspended.
            polling_interval: Polling interval used when the events stream is
                unavailable.
            on_ready: Called from the observer thread once the initial state check
                has completed or the observer has failed. May be called more than
                once.
            on_exit: Called from the observer thread once the observer has shut
                down.
        """
        self._flow_run_id = flow_run_id
        self._suspension_request = suspension_request
        self._polling_interval = polling_interval
        self._on_ready = on_ready
        self._on_exit = on_exit
        self._lock = threading.Lock()
        self._stop_requested = False
        self._wake_observer: Callable[[], object] | None = None
        self._context = contextvars.copy_context()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        """Ask the observer to shut down; `on_exit` is called once it has."""
        with self._lock:
            self._stop_requested = True
            if self._wake_observer is not None:
                self._wake_observer()

    def _mark_suspended(self, flow_run_id: UUID, state: State) -> None:
        if not mark_flow_run_suspension_requested(flow_run_id, state):
            self._suspension_request.mark_requested(state)

    async def _observe(self) -> None:
        from prefect._internal.observers import FlowRunSuspendingObserver

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        with self._lock:
            if self._stop_requested:
                stop_event.set()
            self._wake_observer = partial(loop.call_soon_threadsafe, stop_event.set)

        try:
            async with FlowRunSuspendingObserver(
                on_suspended=self._mark_suspended,
                polling_interval=self._polling_interval,
            ) as observer:
                await observer.watch_flow_run_id(self._flow_run_id)
                self._on_ready()
                await stop_event.wait()
        finally:
            # Under the lock so that `stop` never schedules onto a closed loop.
            with self._lock:
                self._wake_observer = None

    def _run(self) -> None:
        try:
            self._context.run(lambda: asyncio.run(self._observe()))
        except Exception:
            get_logger("flow_run_suspension").debug(
                "Flow run suspension observer exited with an exception",
                exc_info=True,
            )
        finally:
            self._on_ready()
            self._on_exit()


@contextmanager
def observe_flow_run_suspension(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
    polling_interval: float = 10,
) -> Generator[None, None, None]:
    ready = threading.Event()
    exited = threading.Event()
    observer = _FlowRunSuspensionObserverThread(
        flow_run_id,
        suspension_request,
        polling_interval,
        on_ready=ready.set,
        on_exit=exited.set,
    )
    observer.start()
    ready.wait()

    try:
        yield
    finally:
        observer.stop()
        exited.wait(timeout=2)


@asynccontextmanager
async def observe_flow_run_suspension_async(
    flow_run_id: UUID,
    suspension_request: FlowRunSuspensionRequest,
    polling_interval: float = 10,
) -> AsyncGenerator[None, None]:
    """
    Async counterpart of `observe_flow_run_suspension`.

    Waits for the observer to start and to shut down without blocking the event
    loop, so other work on the loop, such as other flow runs, keeps running
    meanwhile.
    """
    loop = asyncio.get_running_loop()
    ready: asyncio.Future[None] = loop.create_future()
    exited: asyncio.Future[None] = loop.create_future()

    def resolve_threadsafe(future: asyncio.Future[None]) -> None:
        try:
            loop.call_soon_threadsafe(_resolve_future, future)
        except RuntimeError:
            # The loop has closed, so nothing is waiting on the future anymore.
            pass

    observer = _FlowRunSuspensionObserverThread(
        flow_run_id,
        suspension_request,
        polling_interval,
        on_ready=lambda: resolve_threadsafe(ready),
        on_exit=lambda: resolve_threadsafe(exited),
    )
    observer.start()

    try:
        await ready
        yield
    finally:
        observer.stop()
        await asyncio.wait([exited], timeout=2)


def _resolve_future(future: asyncio.Future[None]) -> None:
    if not future.done():
        future.set_result(None)
