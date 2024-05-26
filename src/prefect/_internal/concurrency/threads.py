"""
Utilities for managing worker threads.
"""

import asyncio
import atexit
import concurrent.futures
import itertools
import queue
import threading
from typing import List, Optional

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.calls import Call, Portal
from prefect._internal.concurrency.cancellation import CancelledError
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.primitives import Event


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
        self._queue = queue.Queue()
        self._run_once: bool = run_once
        self._started: bool = False
        self._submitted_count: int = 0
        self._lock = threading.Lock()

        if not daemon:
            atexit.register(self.shutdown)

    def start(self):
        """
        Start the worker thread.
        """
        with self._lock:
            if not self._started:
                self._started = True
                self.thread.start()

    def submit(self, call: Call) -> Call:
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

    def _entrypoint(self):
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
        self._ready_future = concurrent.futures.Future()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_event: Event = Event()
        self._run_once: bool = run_once
        self._submitted_count: int = 0
        self._on_shutdown: List[Call] = []
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

    def submit(self, call: Call) -> Call:
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

            # Submit the call to the event loop
            asyncio.run_coroutine_threadsafe(self._run_call(call), self._loop)

            self._submitted_count += 1
            if self._run_once:
                call.future.add_done_callback(lambda _: self.shutdown())

        return call

    def shutdown(self) -> None:
        """
        Shutdown the worker thread. Does not wait for the thread to stop.
        """
        with self._lock:
            if self._shutdown_event is None:
                return

            self._shutdown_event.set()

    @property
    def name(self) -> str:
        return self.thread.name

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

    async def _run_call(self, call: Call) -> None:
        task = call.run()
        if task is not None:
            await task

    def add_shutdown_call(self, call: Call) -> None:
        self._on_shutdown.append(call)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.shutdown()


# the GLOBAL LOOP is used for background services, like logs
GLOBAL_LOOP: Optional[EventLoopThread] = None
# the RUN SYNC LOOP is used exclusively for running async functions in a sync context via asyncutils.run_sync
RUN_SYNC_LOOP: Optional[EventLoopThread] = None


def get_global_loop() -> EventLoopThread:
    """
    Get the global loop thread.

    Creates a new one if there is not one available.
    """
    global GLOBAL_LOOP

    # Create a new worker on first call or if the existing worker is dead
    if (
        GLOBAL_LOOP is None
        or not GLOBAL_LOOP.thread.is_alive()
        or GLOBAL_LOOP._shutdown_event.is_set()
    ):
        GLOBAL_LOOP = EventLoopThread(daemon=True, name="GlobalEventLoopThread")
        GLOBAL_LOOP.start()

    return GLOBAL_LOOP


def in_global_loop() -> bool:
    """
    Check if called from the global loop.
    """
    if GLOBAL_LOOP is None:
        # Avoid creating a global loop if there isn't one
        return False

    return get_global_loop()._loop == get_running_loop()


def get_run_sync_loop() -> EventLoopThread:
    """
    Get the run_sync loop thread.

    Creates a new one if there is not one available.
    """
    global RUN_SYNC_LOOP

    # Create a new worker on first call or if the existing worker is dead
    if (
        RUN_SYNC_LOOP is None
        or not RUN_SYNC_LOOP.thread.is_alive()
        or RUN_SYNC_LOOP._shutdown_event.is_set()
    ):
        RUN_SYNC_LOOP = EventLoopThread(daemon=True, name="RunSyncEventLoopThread")
        RUN_SYNC_LOOP.start()

    return RUN_SYNC_LOOP


def in_run_sync_loop() -> bool:
    """
    Check if called from the global loop.
    """
    if RUN_SYNC_LOOP is None:
        # Avoid creating a global loop if there isn't one
        return False

    return get_run_sync_loop()._loop == get_running_loop()


def wait_for_global_loop_exit(timeout: Optional[float] = None) -> None:
    """
    Shutdown the global loop and wait for it to exit.
    """
    loop_thread = get_global_loop()
    loop_thread.shutdown()

    if threading.get_ident() == loop_thread.thread.ident:
        raise RuntimeError("Cannot wait for the loop thread from inside itself.")

    loop_thread.thread.join(timeout)
