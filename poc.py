import collections
import concurrent.futures
import contextlib
import contextvars
import dataclasses
import functools
import inspect
import logging
import queue
import threading
import typing
import uuid

import anyio
import anyio.abc

MAIN_THREAD = threading.get_ident()
T = typing.TypeVar("T")

logging.basicConfig(level="DEBUG", format="{threadName: <12} > {message}", style="{")
logging.getLogger("asyncio").setLevel("INFO")

logger = logging.getLogger(__name__)
logger.debug("Logging initialized")

threadlocals = threading.local()
current_runtime: contextvars.ContextVar["Runtime"] = contextvars.ContextVar(
    "current_runtime"
)


def get_current_portal() -> typing.Optional[anyio.abc.BlockingPortal]:
    return getattr(threadlocals, "current_portal", None)


def set_current_portal(portal: anyio.abc.BlockingPortal, name: str = None) -> None:
    thread = threading.current_thread()
    if thread.ident != portal._event_loop_thread_id:
        raise RuntimeError(
            "Attempted to set current portal to portal running in another thread. Only a portal in the current thread can be used."
        )
    if name:
        thread.name = name
    threadlocals.current_portal = portal


class PortalEvent(anyio.abc.Event):
    """
    An async event that threadsafe. Requires use of a blocking portal.
    """

    def __init__(self) -> None:
        super().__init__()
        self._portal = get_current_portal()
        if not self._portal:
            raise RuntimeError(
                "No portal found in current thread. Portal events cannot be created outside of a portal."
            )

    def __new__(cls):
        # Override anyio's creation of a backend specific type, placing that at `_implementation` instead.
        instance = object.__new__(cls)
        instance._implementation = super().__new__(cls)
        return instance

    def set(self):
        """Set the flag, notifying all listeners."""
        if get_current_portal() == self._portal:
            return self._implementation.set()
        else:
            return self._portal.call(self._implementation.set)

    def is_set(self) -> bool:
        """Return ``True`` if the flag is set, ``False`` if not."""
        if get_current_portal() == self._portal:
            return self._implementation.is_set()
        else:
            return self._portal.call(self._implementation.is_set)

    async def wait(self) -> None:
        """
        Wait until the flag has been set.

        If the flag has already been set when this method is called, it returns immediately.
        """
        return await self._implementation.wait()


class PortalFuture:
    """
    A future representing work passed to and from a portal.
    """

    def __init__(self, future: typing.Optional[concurrent.futures.Future] = None):
        self._done_event = PortalEvent()
        self._future = future or concurrent.futures.Future()
        self._future.add_done_callback(self._set_done_event)

    def _set_done_event(self, future: "concurrent.futures.Future"):
        assert future is self._future
        logger.debug("Future %s done", future)
        self._done_event.set()

    async def result(self):
        """Get the result of the future."""
        await self._done_event.wait()
        return self._future.result()

    def set_running_or_notify_cancel(self):
        return self._future.set_running_or_notify_cancel()

    def set_result(self, result: typing.Any):
        return self._future.set_result(result)

    def set_exception(self, exception: BaseException):
        return self._future.set_exception(exception)


@contextlib.contextmanager
def start_portal_thread(name: str = None):
    """
    Run a new thread with an event loop.
    """
    with anyio.start_blocking_portal() as portal:
        portal.call(set_current_portal, portal, name)
        yield portal


@dataclasses.dataclass
class WorkItem:
    """
    A call to perform in a thread.

    """

    future: PortalFuture
    fn: typing.Callable
    args: typing.Tuple
    kwargs: typing.Dict

    def run(self):
        if not self.future.set_running_or_notify_cancel():
            return

        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)


class Runtime:
    def __init__(self) -> None:
        self._exit_stack = contextlib.ExitStack()
        self._runtime_loop: anyio.abc.BlockingPortal = None
        self._worker_loops: typing.Dict[int, anyio.abc.BlockingPortal] = {}
        self._worker_locks: typing.Dict[int, threading.Lock] = collections.defaultdict(
            threading.Lock
        )
        self._work_queue: queue.Queue[WorkItem] = queue.Queue()
        self._thread = threading.current_thread()

    def __enter__(self):
        self._exit_stack.__enter__()
        self._runtime_loop = self._exit_stack.enter_context(
            start_portal_thread(name="Runtime")
        )
        self._context_token = current_runtime.set(self)
        return self

    def __exit__(self, *exc_info):
        current_runtime.reset(self._context_token)
        self._exit_stack.close()

    def run_async(
        self,
        fn: typing.Callable[..., typing.Awaitable[T]],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> T:
        logger.debug("Scheduling async task %s", fn)
        # Schedule the async task on a portal thread
        future = self._runtime_loop.start_task_soon(
            functools.partial(fn, *args, **kwargs)
        )

        # When the future is done, push a null item to the queue to signal exit
        future.add_done_callback(lambda _: self._work_queue.put_nowait(None))

        # Watch for work to do while the future is running
        self._consume_work_queue()

        return future.result()

    async def run_sync_in_main_thread(
        self, fn: typing.Callable[..., T], *args: typing.Any, **kwargs: typing.Any
    ) -> T:
        """
        Schedule work on the main thread from the runtime thread.

        The async function must be running with `run_async`.
        """
        logger.debug("Scheduling sync task %s", fn)
        future = PortalFuture()

        work_item = WorkItem(future=future, fn=fn, args=args, kwargs=kwargs)
        self._work_queue.put_nowait(work_item)

        # Unblock the event loop thread, wait for completion of the task
        logger.debug("Waiting for completion...")
        return await future.result()

    async def run_async_in_worker(
        self, fn: typing.Callable[..., T], *args: typing.Any, **kwargs: typing.Any
    ):
        """
        Schedule work on a worker event loop from the runtime event loop.

        The user may make blocking synchronous calls and we must be careful to avoid
        blocking the runtime event loop. Even if the user's call does not perform IO,
        it may need to block when calling into the runtime.
        """
        with self._get_async_worker() as worker:
            future = worker.start_task_soon(functools.partial(fn, *args, **kwargs))
            return await PortalFuture(future).result()

    def run_async_from_worker(
        self, fn: typing.Callable[..., T], *args: typing.Any, **kwargs: typing.Any
    ):
        """
        Schedule work on the runtime event loop from a worker event loop.
        """
        future = self._runtime_loop.start_task_soon(
            functools.partial(fn, *args, **kwargs)
        )
        with self._worker_locks[get_current_portal()._event_loop_thread_id]:
            return future.result()

    @contextlib.contextmanager
    def _get_async_worker(self):
        """
        Get a worker loop.

        If all worker loops are blocked, create a temporary new worker.
        """
        for worker_id, loop in self._worker_loops.items():
            lock = self._worker_locks.get(worker_id)
            if not lock or not lock.locked():
                yield loop
                break
        else:
            logger.debug("Created new async worker")
            with start_portal_thread(
                name=f"Worker-{len(self._worker_loops) + 1}"
            ) as loop:
                self._worker_loops[loop._event_loop_thread_id] = loop
                yield loop
                self._worker_loops.pop(loop._event_loop_thread_id)

    def _consume_work_queue(self):
        """
        Read work from the work queue until a null item is seen.
        """
        while True:
            logger.debug("Waiting for work...")
            work_item = self._work_queue.get()
            if work_item is None:
                break

            logger.debug("Running work item %s", work_item)
            work_item.run()
            del work_item

    def in_main_thread(self):
        return self._thread.ident == threading.get_ident()


@dataclasses.dataclass
class Run:
    id: uuid.UUID
    name: str


@dataclasses.dataclass
class Workflow:
    name: str
    fn: typing.Callable

    def __call__(self, **parameters):
        return entrypoint(self, parameters)


def entrypoint(workflow, parameters):
    logger.debug(f"Entrypoint for {workflow.name!r}")
    runtime = current_runtime.get(None)
    if inspect.iscoroutinefunction(workflow.fn) and (
        not runtime or not runtime.in_main_thread()
    ):
        logger.debug("Entrypoint: Returning coroutine")
        return workflow.fn(**parameters)
    elif runtime and runtime.in_main_thread():
        logger.debug("Entrypoint: Running with runtime")
        return runtime.run_async(run_workflow, runtime, workflow, parameters)

    elif runtime and not runtime.in_main_thread():
        logger.debug("Entrypoint: Oh.. we're already in the async thread.. now what?")
        return runtime.run_async_from_worker(
            run_workflow, runtime, workflow, parameters
        )

    else:
        logger.debug("Entrypoint: Creating new runtime")
        with Runtime() as runtime:
            return runtime.run_async(run_workflow, runtime, workflow, parameters)


async def run_workflow(runtime: Runtime, workflow: Workflow, parameters: dict):
    run = await create_run(workflow)
    return await orchestrate_run(runtime, workflow, run, parameters)


async def create_run(workflow: Workflow) -> Run:
    return Run(id=uuid.uuid4(), name=workflow.name)


async def orchestrate_run(
    runtime: Runtime,
    workflow: Workflow,
    run: Run,
    parameters: dict,
):
    logger.debug("Orchestrating workflow %r", workflow.name)
    runtime = current_runtime.get()
    if inspect.iscoroutinefunction(workflow.fn):
        # Send user coroutines to another event loop that we do not "trust" in so the
        # engine event loop is never blocked
        logger.debug("Sending task to worker loop")
        result = await runtime.run_async_in_worker(workflow.fn, **parameters)
    else:
        result = await runtime.run_sync_in_main_thread(workflow.fn, **parameters)

    return result


if __name__ == "__main__":

    def foo():
        logger.debug("Running foo!")
        return 1

    async def bar():
        logger.debug("Running bar!")
        return 2

    def foobar():
        logger.debug("Runing foobar")
        return foo() + bar()

    async def afoobar():
        logger.debug("Running afoobar!")
        # result = foo()
        aresult = await bar()

        # Failing: Sync (new runtime, in main thread) -> Async (in async worker) -> Sync (in main thread) -> Async (in async worker — blocked)
        result = foobar()
        return result + aresult

    def nested_foobar():
        logger.debug("Running nested_foobar")
        result = foobar()
        aresult = afoobar()
        return result + aresult

    async def anested_foobar():
        logger.debug("Running anested_foobar")
        result = foobar()
        aresult = await afoobar()
        return result + aresult

    def tripled_foobar():
        logger.debug("Running tripled_foobar")
        result = nested_foobar()
        aresult = anested_foobar()
        return result + aresult

    async def atripled_foobar():
        logger.debug("Running atripled_foobar")
        result = nested_foobar()
        aresult = await anested_foobar()
        return result + aresult

    foo = Workflow(name="foo", fn=foo)
    bar = Workflow(name="bar", fn=bar)
    foobar = Workflow(name="foobar", fn=foobar)
    afoobar = Workflow(name="afoobar", fn=afoobar)
    nested_foobar = Workflow(name="nested_foobar", fn=nested_foobar)
    anested_foobar = Workflow(name="anested_foobar", fn=anested_foobar)
    tripled_foobar = Workflow(name="tripled_foobar", fn=tripled_foobar)
    atripled_foobar = Workflow(name="atripled_foobar", fn=atripled_foobar)

    print("---- Sync ----")
    result = foo()
    print(result)

    print("---- Async ----")
    result = anyio.run(bar)
    print(result)

    print("---- Sync parent ----")
    result = foobar()
    print(result)

    print("---- Async parent ----")
    result = anyio.run(afoobar)
    print(result)

    print("---- Sync (double nested) ----")
    result = nested_foobar()
    print(result)

    print("---- Async (double nested) ----")
    result = anyio.run(anested_foobar)
    print(result)

    print("---- Sync (triple nested) ----")
    result = tripled_foobar()
    print(result)

    print("---- Async (triple nested) ----")
    result = anyio.run(atripled_foobar)
    print(result)
