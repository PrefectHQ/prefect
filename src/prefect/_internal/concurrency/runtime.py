import asyncio
import concurrent.futures
import contextlib
import threading
from typing import Optional, TypeVar

from typing_extensions import ParamSpec

from prefect._internal.concurrency.executor import Executor
from prefect._internal.concurrency.primitives import Event

T = TypeVar("T")
P = ParamSpec("P")


threadlocals = threading.local()


def _initialize_worker_process():
    threadlocals.is_worker_process = True
    threading.current_thread().name = "RuntimeWorkerProcess"


def _initialize_worker_thread():
    threadlocals.is_worker_thread = True


class RuntimeThread(threading.Thread):
    def __init__(self, name: str = "RuntimeThread"):
        super().__init__(name=name, daemon=True)

        # Configure workers
        self._worker_threads = Executor(
            worker_type="thread",
            thread_name_prefix="RuntimeWorkerThread-",
            initializer=_initialize_worker_thread,
        )
        self._worker_processes = Executor(
            worker_type="process", initializer=_initialize_worker_process
        )
        self._ready_future = concurrent.futures.Future()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self):
        """
        Start the thread and wait until the event loop is ready.
        """
        super().start()
        # Extends the typical thread start event to wait until `run` is ready and
        # raise any errors encountered during setup
        self._ready_future.result()

    def run(self):
        """
        Entrypoint for the thread.

        Immediately create a new event loop and pass control to `run_until_shutdown`.
        """
        asyncio.run(self._run_until_shutdown())

    async def _run_until_shutdown(self):
        threadlocals.is_runtime = True
        self._loop = asyncio.get_running_loop()
        self._shutdown_event = Event()
        async with contextlib.AsyncExitStack() as stack:
            try:
                await stack.enter_async_context(self._worker_threads)
                await stack.enter_async_context(self._worker_processes)
                self._ready_future.set_result(True)
            except Exception as exc:
                self._ready_future.set_exception(exc)
                return

            await self._shutdown_event.wait()

    def submit_to_worker_process(
        self, __fn, *args, **kwargs
    ) -> concurrent.futures.Future:
        return self._worker_processes.submit(__fn, *args, **kwargs)

    def submit_to_worker_thread(
        self, __fn, *args, **kwargs
    ) -> concurrent.futures.Future:
        return self._worker_threads.submit(__fn, *args, **kwargs)

    def submit_to_loop(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        assert self._loop is not None, "Runtime thread not ready: no event loop."
        return asyncio.run_coroutine_threadsafe(__fn(*args, **kwargs), self._loop)

    def shutdown(self) -> None:
        self._shutdown_event.set()


RUNTIME_THREAD = None


def get_runtime_thread() -> RuntimeThread:
    global RUNTIME_THREAD
    if RUNTIME_THREAD is None:
        RUNTIME_THREAD = RuntimeThread()
        RUNTIME_THREAD.start()
    return RUNTIME_THREAD
