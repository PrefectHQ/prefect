"""
Utilities for managing worker threads.
"""
import asyncio
import atexit
import concurrent.futures
import queue
import threading
from typing import Optional

from prefect._internal.concurrency.calls import Call, Portal
from prefect._internal.concurrency.primitives import Event
from prefect.logging import get_logger

logger = get_logger("prefect._internal.concurrency.threads")


class WorkerThread(Portal):
    """
    A portal to a worker running on a thread.
    """

    def __init__(
        self, name: str = "WorkerThread", daemon: bool = False, run_once: bool = False
    ):
        self.thread = threading.Thread(
            name=name, daemon=daemon, target=self._entrypoint
        )
        self._queue = queue.Queue()
        self._run_once: bool = run_once
        self._started: bool = False
        self._submitted_count: int = 0

        if not daemon:
            atexit.register(self.shutdown)

    def start(self):
        """
        Start the worker thread.
        """
        self.thread.start()

    def submit(self, call: Call) -> Call:
        if self._submitted_count > 0 and self._run_once:
            raise RuntimeError(
                "Worker configured to only run once. A call has already been submitted."
            )

        # Start on first submission
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
        except BaseException:
            # Log exceptions that crash the thread
            logger.exception("%s encountered exception", self.name)
            raise

    def _run_until_shutdown(self):
        self._started = True
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

        if not daemon:
            atexit.register(self.shutdown)

    def start(self):
        """
        Start the worker thread; raises any exceptions encountered during startup.
        """
        self.thread.start()
        # Wait for the worker to be ready
        self._ready_future.result()

    def submit(self, call: Call) -> Call:
        if self._submitted_count > 0 and self._run_once:
            raise RuntimeError(
                "Worker configured to only run once. A call has already been submitted."
            )

        if self._loop is None:
            self.start()

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

    async def _run_call(self, call: Call) -> None:
        task = call.run()
        if task is not None:
            await task

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.shutdown()


GLOBAL_LOOP_PORTAL: Optional[EventLoopThread] = None


def get_global_loop() -> EventLoopThread:
    global GLOBAL_LOOP_PORTAL

    # Create a new worker on first call or if the existing worker is dead
    if GLOBAL_LOOP_PORTAL is None or not GLOBAL_LOOP_PORTAL.thread.is_alive():
        GLOBAL_LOOP_PORTAL = EventLoopThread(daemon=True, name="GlobalEventLoopThread")
        GLOBAL_LOOP_PORTAL.start()

    return GLOBAL_LOOP_PORTAL


def wait_for_global_loop_exit() -> None:
    portal = get_global_loop()
    portal.shutdown()

    if threading.get_ident() == portal.thread.ident:
        raise RuntimeError("Cannot wait for the global thread from inside itself.")

    portal.thread.join()
