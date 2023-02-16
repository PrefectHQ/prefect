import asyncio
import concurrent.futures
import contextlib
import contextvars
import dataclasses
import inspect
import os
import threading
from queue import Queue
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.executor import Executor
from prefect._internal.concurrency.primitives import Event
from prefect.context import ContextModel

T = TypeVar("T")
P = ParamSpec("P")


threadlocals = threading.local()


def _initialize_worker_process():
    threadlocals.is_worker_process = True
    threading.current_thread().name = "RuntimeWorkerProcess"


def _initialize_worker_thread():
    threadlocals.is_worker_thread = True


class _FutureContext(ContextModel):
    __var__ = contextvars.ContextVar("future-context")
    callback_queue: Union[Queue, asyncio.Queue]


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
        loop = asyncio.get_running_loop()
        try:
            # Call the function in the context; this is not necessary if the function
            # is a standard cortouine function but if it's a synchronous function that
            # returns a coroutine we want to ensure the correct context is available
            coro = self.context.run(self.fn, *self.args, **self.kwargs)

            # Run the coroutine in a new task to run with the correct async context
            task = self.context.run(loop.create_task, coro)
            result = await task

        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)


class _RuntimeLoopThread(threading.Thread):
    def __init__(self, name: str = "RuntimeLoopThread"):
        super().__init__(name=name)

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


class Runtime:
    def __init__(self) -> None:
        self._owner_loop = get_running_loop()
        self._owner_thread_id = threading.get_ident()
        self._owner_process_id = os.getpid()

        # A thread for an isolated event loop
        self._loop_thread = _RuntimeLoopThread()

    def run_in_thread(
        self, __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """
        Run a function in a worker thread.

        The worker thread may send work back to this thread while waiting for the
        result of this call.

        If the runtime is owned by a thread with a running event loop, this returns
        a coroutine.

        Returns the result of the function call.
        """
        queue = self._get_callback_queue()
        with _FutureContext(callback_queue=queue):
            future = self._loop_thread.submit_to_worker_thread(__fn, *args, **kwargs)
        return self._wait_for_future(future, queue)

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
        future = self._loop_thread.submit_to_worker_process(__fn, *args, **kwargs)
        return asyncio.wrap_future(future) if self._owner_loop else future.result()

    def run_in_loop(
        self,
        __fn: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """
        Run a function in the runtime event loop.

        The function may send work back to this thread while waiting for the result of
        this call.

        If this thread has a running event loop, this returns a coroutine.

        Returns:
            The result of the function call.
        """

        queue = self._get_callback_queue()
        with _FutureContext(callback_queue=queue):
            future = self._loop_thread.submit_to_loop(__fn, *args, **kwargs)
        return self._wait_for_future(future, queue)

    def _get_callback_queue(self) -> Union[Queue, asyncio.Queue]:
        return Queue() if self._owner_loop is None else asyncio.Queue()

    def _put_in_callback_queue(
        self, queue: Union[Queue, asyncio.Queue], item: Any
    ) -> None:
        """
        Put an item in the given callback queue.

        Ensures async queues are used in a threadsafe manner.
        """
        if isinstance(queue, asyncio.Queue):
            self._owner_loop.call_soon_threadsafe(queue.put_nowait, item)
        else:
            queue.put_nowait(item)

    def _wait_for_future(
        self, future: "concurrent.futures.Future[T]", queue: Queue
    ) -> T:
        # Select the correct watcher for this context
        watcher = (
            self._wait_for_future_async
            if self._owner_loop
            else self._wait_for_future_sync
        )

        # Trigger shutdown of the watcher on completion of the future
        future.add_done_callback(lambda _: self._put_in_callback_queue(queue, None))
        return watcher(future, queue)

    def _wait_for_future_sync(self, future, queue):
        while True:
            work_item = queue.get()
            if work_item is None:
                break

            work_item.run()
            del work_item

        return future.result()

    async def _wait_for_future_async(self, future, queue):
        while True:
            # Retrieve the next work item from the queue without blocking the event loop
            work_item = await queue.get()
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
        **kwargs: P.kwargs,
    ) -> "concurrent.futures.Future[T]":

        # Safety check thread and process identifiers
        if threading.get_ident() == self._owner_thread_id:
            raise RuntimeError(
                "Work cannot be submitted back to the runtime unless you are in "
                "different thread."
            )
        if os.getpid() != self._owner_process_id:
            # Note: The runtime itself cannot be pickled, so you'd be hard pressed to
            #       call this from another process.
            raise RuntimeError(
                "Work cannot be submitted back to the runtime from another process."
            )

        #  Safety check sync / async
        if self._owner_loop and not inspect.iscoroutinefunction(__fn):
            raise RuntimeError(
                f"The runtime is async but {__fn.__name__!r} is sync. "
                "Work returned to the runtime must match type."
            )
        if not self._owner_loop and inspect.iscoroutinefunction(__fn):
            raise RuntimeError(
                f"The runtime is sync but {__fn.__name__!r} is async. "
                "Work returned to the runtime must match type."
            )

        future = concurrent.futures.Future()

        context = _FutureContext.get()
        if context is None:
            raise RuntimeError(
                "No runtime future context found. "
                "Work cannot be sent back to the runtime unless the runtime was used "
                "to execute the current call."
            )

        self._put_in_callback_queue(
            context.callback_queue,
            _WorkItem(
                future=future,
                fn=__fn,
                args=args,
                kwargs=kwargs,
                context=contextvars.copy_context(),
            ),
        )

        return future

    def __enter__(self):
        self._loop_thread.start()
        return self

    def __exit__(self, *exc_info):
        self._loop_thread.shutdown()
        self._loop_thread.join()
