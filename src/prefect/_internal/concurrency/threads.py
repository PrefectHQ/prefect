"""
Utilities for managing worker threads.
"""
import asyncio
import atexit
import concurrent.futures
import threading
from typing import Optional

from prefect._internal.concurrency.calls import Call, Portal
from prefect._internal.concurrency.primitives import Event
from prefect.logging import get_logger

logger = get_logger("prefect._internal.concurrency.calls")


class WorkerThread(Portal):
    """
    A portal to a worker running on a thread with an event loop.
    """

    def __init__(
        self, name: str = "WorkerThread", daemon: bool = False, run_once: bool = False
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
        call.set_portal(self)

        self._loop.call_soon_threadsafe(call.run)
        self._submitted_count += 1
        if self._run_once:
            call.future.add_done_callback(lambda _: self.shutdown())

        return call

    def shutdown(self) -> None:
        """
        Shutdown the worker thread. Does not wait for the thread to stop.
        """
        if not self._shutdown_event:
            return

        self._shutdown_event.set()
        # TODO: Consider blocking on `thread.join` here?

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

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.shutdown()


GLOBAL_THREAD_PORTAL: Optional[WorkerThread] = None


def get_global_thread_portal() -> WorkerThread:
    global GLOBAL_THREAD_PORTAL

    # Create a new worker on first call or if the existing worker is dead
    if GLOBAL_THREAD_PORTAL is None or not GLOBAL_THREAD_PORTAL.thread.is_alive():
        GLOBAL_THREAD_PORTAL = WorkerThread(daemon=True, name="GlobalWorkerThread")
        GLOBAL_THREAD_PORTAL.start()

    return GLOBAL_THREAD_PORTAL
