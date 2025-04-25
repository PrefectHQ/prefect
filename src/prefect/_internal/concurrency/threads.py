"""
Utilities for managing worker threads.
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import itertools
import queue
import threading
from typing import Any, Optional

from typing_extensions import TypeVar

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.calls import Call, Portal
from prefect._internal.concurrency.cancellation import CancelledError
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.primitives import Event

T = TypeVar("T", infer_variance=True)


class WorkerThread(Portal):
    """
    A portal to a worker running on a thread.
    """

    # Used for unique thread names by default
    _counter = itertools.count().__next__

    def __init__(
        self, name: Optional[str] = None, daemon: bool = False, run_once: bool = False
    ):
        name = name or f"WorkerThread-{self._counter()}"

        self.thread = threading.Thread(
            name=name, daemon=daemon, target=self._entrypoint
        )
        self._queue: queue.Queue[Optional[Call[Any]]] = queue.Queue()
        self._run_once: bool = run_once
        self._started: bool = False
        self._submitted_count: int = 0
        self._lock = threading.Lock()

        if not daemon:
            atexit.register(self.shutdown)

    def start(self) -> None:
        """
        Start the worker thread.
        """
        with self._lock:
            if not self._started:
                self._started = True
                self.thread.start()

    def submit(self, call: Call[T]) -> Call[T]:
        if self._submitted_count > 0 and self._run_once:
            raise RuntimeError(
                "Worker configured to only run once. A call has already been submitted."
            )

        # Start on first submission if not started
        if not self._started:
            self.start()

        # Track the portal running the call
        call.set_runner(self)

        # Put the call in the queue
        self._queue.put_nowait(call)

        self._submitted_count += 1
        if self._run_once:
            call.future.add_done_callback(lambda _: self.shutdown())

        return call

    def shutdown(self) -> None:
        """
        Shutdown the worker thread. Does not wait for the thread to stop.
        """
        self._queue.put_nowait(None)

    @property
    def name(self) -> str:
        return self.thread.name

    def _entrypoint(self) -> None:
        """
        Entrypoint for the thread.
        """
        try:
            self._run_until_shutdown()
        except CancelledError:
            logger.exception("%s was cancelled", self.name)
        except BaseException:
            # Log exceptions that crash the thread
            logger.exception("%s encountered exception", self.name)
            raise

    def _run_until_shutdown(self):
        while True:
            call = self._queue.get()
            if call is None:
                logger.info("Exiting worker thread %r", self.name)
                break  # shutdown requested

            task = call.run()
            assert task is None  # calls should never return a coroutine in this worker
            del call

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.shutdown()


class EventLoopThread(Portal):
    """
    A portal to a worker running on a thread with an event loop.
    """

    def __init__(
        self,
        name: str = "EventLoopThread",
        daemon: bool = False,
        run_once: bool = False,
    ):
        self.thread = threading.Thread(
            name=name, daemon=daemon, target=self._entrypoint
        )
        self._ready_future: concurrent.futures.Future[bool] = (
            concurrent.futures.Future()
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_event: Event = Event()
        self._run_once: bool = run_once
        self._submitted_count: int = 0
        self._on_shutdown: list[Call[Any]] = []
        self._lock = threading.Lock()

        if not daemon:
            atexit.register(self.shutdown)

    def start(self):
        """
        Start the worker thread; raises any exceptions encountered during startup.
        """
        with self._lock:
            if self._loop is None:
                self.thread.start()
                self._ready_future.result()

    def submit(self, call: Call[T]) -> Call[T]:
        if self._loop is None:
            self.start()

        with self._lock:
            if self._submitted_count > 0 and self._run_once:
                raise RuntimeError(
                    "Worker configured to only run once. A call has already been"
                    " submitted."
                )

            if self._shutdown_event.is_set():
                raise RuntimeError("Worker is shutdown.")

            # Track the portal running the call
            call.set_runner(self)

            if self._run_once:
                call.future.add_done_callback(lambda _: self.shutdown())

            # Submit the call to the event loop
            assert self._loop is not None
            asyncio.run_coroutine_threadsafe(self._run_call(call), self._loop)
            self._submitted_count += 1

        return call

    def shutdown(self) -> None:
        """
        Shutdown the worker thread. Does not wait for the thread to stop.
        """
        with self._lock:
            self._shutdown_event.set()

    @property
    def name(self) -> str:
        return self.thread.name

    @property
    def running(self) -> bool:
        return not self._shutdown_event.is_set()

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    def _entrypoint(self):
        """
        Entrypoint for the thread.

        Immediately create a new event loop and pass control to `run_until_shutdown`.
        """
        try:
            asyncio.run(self._run_until_shutdown())
        except BaseException:
            # Log exceptions that crash the thread
            logger.exception("%s encountered exception", self.name)
            raise

    async def _run_until_shutdown(self):
        try:
            self._loop = asyncio.get_running_loop()
            self._ready_future.set_result(True)
        except Exception as exc:
            self._ready_future.set_exception(exc)
            return

        await self._shutdown_event.wait()

        for call in self._on_shutdown:
            await self._run_call(call)

        # Empty the list to allow calls to be garbage collected. Issue #10338.
        self._on_shutdown = []

    async def _run_call(self, call: Call[Any]) -> None:
        task = call.run()
        if task is not None:
            await task

    def add_shutdown_call(self, call: Call[Any]) -> None:
        self._on_shutdown.append(call)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.shutdown()


# the GLOBAL LOOP is used for background services, like logs
_global_loop: Optional[EventLoopThread] = None
# the RUN SYNC LOOP is used exclusively for running async functions in a sync context via asyncutils.run_sync
_run_sync_loop: Optional[EventLoopThread] = None


def get_global_loop() -> EventLoopThread:
    """
    Get the global loop thread.

    Creates a new one if there is not one available.
    """
    global _global_loop

    # Create a new worker on first call or if the existing worker is dead
    if (
        _global_loop is None
        or not _global_loop.thread.is_alive()
        or not _global_loop.running
    ):
        _global_loop = EventLoopThread(daemon=True, name="GlobalEventLoopThread")
        _global_loop.start()

    return _global_loop


def in_global_loop() -> bool:
    """
    Check if called from the global loop.
    """
    if _global_loop is None:
        # Avoid creating a global loop if there isn't one
        return False

    return getattr(get_global_loop(), "_loop") == get_running_loop()


def get_run_sync_loop() -> EventLoopThread:
    """
    Get the run_sync loop thread.

    Creates a new one if there is not one available.
    """
    global _run_sync_loop

    # Create a new worker on first call or if the existing worker is dead
    if (
        _run_sync_loop is None
        or not _run_sync_loop.thread.is_alive()
        or not _run_sync_loop.running
    ):
        _run_sync_loop = EventLoopThread(daemon=True, name="RunSyncEventLoopThread")
        _run_sync_loop.start()

    return _run_sync_loop


def in_run_sync_loop() -> bool:
    """
    Check if called from the global loop.
    """
    if _run_sync_loop is None:
        # Avoid creating a global loop if there isn't one
        return False

    return getattr(get_run_sync_loop(), "_loop") == get_running_loop()


def wait_for_global_loop_exit(timeout: Optional[float] = None) -> None:
    """
    Shutdown the global loop and wait for it to exit.
    """
    loop_thread = get_global_loop()
    loop_thread.shutdown()

    if threading.get_ident() == loop_thread.thread.ident:
        raise RuntimeError("Cannot wait for the loop thread from inside itself.")

    loop_thread.thread.join(timeout)
