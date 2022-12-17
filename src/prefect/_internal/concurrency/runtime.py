import asyncio
import concurrent.futures
import contextvars
import dataclasses
import inspect
import threading
from queue import Queue
from typing import Any, Awaitable, Callable, Dict, Tuple, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.executor import Executor
from prefect._internal.concurrency.primitives import Event

T = TypeVar("T")
P = ParamSpec("P")


@dataclasses.dataclass
class _WorkItem:
    future: concurrent.futures.Future
    fn: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    context: contextvars.Context

    def run(self):
        """
        Execute the work item.

        All exceptions during execution of the work item are captured and attached to
        the future.
        """
        # Do not execute if the future is cancelled
        if not self.future.set_running_or_notify_cancel():
            return

        # Execute the work and set the result on the future
        if inspect.iscoroutinefunction(self.fn):
            return self._run_async()
        else:
            return self._run_sync()

    def _run_sync(self):
        try:
            result = self.context.run(self.fn, *self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)

    async def _run_async(self):
        try:
            result = await self.context.run(self.fn, *self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)


class _RuntimeThread(threading.Thread):
    def __init__(self, name: str = "PrefectRuntime"):
        super().__init__(name=name)
        self._worker_threads = Executor(worker_type="thread")
        self._worker_processes = Executor(worker_type="process")
        self._ready_event = threading.Event()
        self._loop = None

    def start(self):
        """
        Start the thread and wait until the event loop is ready.
        """
        super().start()
        # Extends the typical thread start event to include a readiness event set from
        # within the event loop.
        self._ready_event.wait()

    def run(self):
        """
        Entrypoint for the thread.

        Immediately create a new event loop and pass control to `run_until_shutdown`.
        """
        asyncio.run(self._run_until_shutdown())

    async def _run_until_shutdown(self):
        self._loop = asyncio.get_running_loop()
        self._shutdown_event = Event()
        async with self._worker_threads:
            async with self._worker_processes:
                self._ready_event.set()
                await self._shutdown_event.wait()

    def submit_to_process(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        return self._worker_threads.submit(__fn, *args, **kwargs)

    def submit_to_thread(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        return self._worker_threads.submit(__fn, *args, **kwargs)

    def submit_to_loop(self, __fn, *args, **kwargs) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(__fn(*args, **kwargs), self._loop)

    def shutdown(self) -> None:
        self._shutdown_event.set()


class Runtime:
    def __init__(self) -> None:
        self._runtime = _RuntimeThread()
        self._work_queue = Queue()
        self._watcher = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="PrefectRuntimeWatcher-"
        )
        self._owner_loop = get_running_loop()

    def run_in_thread(
        self, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """
        Run a function in a worker thread.

        The worker thread may send work back to this thread while waiting for the
        result of this call.

        If the runtime is owned by a thread with a running event loop, this returns
        a coroutine

        Returns the result of the function call.
        """
        future = self._runtime.submit_to_thread(__fn, *args, **kwargs)
        return self._wait_for_future(future)

    def run_in_process(
        self, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """
        Run a function in a worker process.

        Unlike `run_in_thread` and `run_in_process`, this method does not allow work to
        be passed back to the this thread.

        If this thread has a running event loop, this returns a coroutine.

        Returns:
            The result of the function call.
        """
        future = self._runtime.submit_to_process(__fn, *args, **kwargs)
        return asyncio.wrap_future(future) if self._owner_loop else future.result()

    def run_in_loop(
        self,
        __fn: Union[Callable[P, Awaitable[T]], Callable[P, T]],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> T:
        """
        Run a function on the runtime thread.

        The function may send work back to this thread while waiting for the result of
        this call.

        If this thread has a running event loop, this returns a coroutine.

        Returns:
            The result of the function call.
        """
        future = self._runtime.submit_to_loop(__fn, *args, **kwargs)
        return self._wait_for_future(future)

    def _wait_for_future(self, future):
        # Select the correct watcher for this context
        watcher = (
            self._wait_for_future_async
            if self._owner_loop
            else self._wait_for_future_sync
        )

        # Trigger shutdown of the watcher on completion of the future
        future.add_done_callback(lambda _: self._work_queue.put_nowait(None))
        return watcher(future)

    def _wait_for_future_sync(self, future):
        while True:
            work_item = self._work_queue.get()
            if work_item is None:
                break

            work_item.run()
            del work_item

        return future.result()

    async def _wait_for_future_async(self, future):
        while True:

            # Retrieve the next work item from the queue without blocking the event loop
            work_item_future = asyncio.wrap_future(
                self._watcher.submit(self._work_queue.get)
            )
            work_item = await work_item_future
            if work_item is None:
                break

            await work_item.run()
            del work_item

        # The future should be complete the queue is closed
        return future.result()

    def submit_from_thread(
        self,
        __fn: Union[Callable[P, Awaitable[T]], Callable[P, T]],
        *args: P.args,
        **kwargs: P.kwargs
    ) -> concurrent.futures.Future[T]:
        future = concurrent.futures.Future()

        self._work_queue.put_nowait(
            _WorkItem(
                future=future,
                fn=__fn,
                args=args,
                kwargs=kwargs,
                context=contextvars.copy_context(),
            )
        )

        return future

    def __enter__(self):
        self._runtime.start()
        return self

    def __exit__(self, *exc_info):
        self._runtime.shutdown()
        self._runtime.join()
