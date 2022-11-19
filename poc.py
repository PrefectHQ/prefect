import contextlib
import dataclasses
import functools
import inspect
import logging
import queue
import threading
import typing
import uuid
from concurrent.futures import Future

import anyio
import anyio.abc

MAIN_THREAD = threading.get_ident()
T = typing.TypeVar("T")

logging.basicConfig(level="DEBUG")

mt_logger = logging.getLogger("main_thread")
as_logger = logging.getLogger("async_thread")
mt_logger.debug("Logging initialized")

threadlocals = threading.local()
threadlocals.runtime = None


@dataclasses.dataclass
class WorkItem:
    future: Future
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
    _work_queue = queue.Queue()
    _wakeup = threading.Event()

    def __init__(self) -> None:
        self._exit_stack = contextlib.ExitStack()
        self._portal: anyio.abc.BlockingPortal = None

    def __enter__(self):
        self._exit_stack.__enter__()
        self._portal = self._exit_stack.enter_context(anyio.start_blocking_portal())
        threadlocals.runtime = self
        return self

    def __exit__(self, *exc_info):
        threadlocals.runtime = None
        self._exit_stack.close()

    def run_async(
        self,
        fn: typing.Callable[..., typing.Awaitable[T]],
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> T:
        mt_logger.debug("Scheduling async task %s", fn)
        # Schedule the async task on a portal thread
        future = self._portal.start_task_soon(functools.partial(fn, *args, **kwargs))

        # When the future is done, fire wakeup. This ensures that if the future does
        # not schedule any work, the main thread will move on.
        future.add_done_callback(lambda _: self._wakeup.set())

        # Watch for work to do while the future is running
        while not future.done():
            self._consume_work_queue()

        return future.result()

    async def run_in_main_thread(
        self, fn: typing.Callable[..., T], *args: typing.Any, **kwargs: typing.Any
    ) -> T:
        """
        Schedule work on the main thread from an async thread.

        The async function must be running with `run_async`.
        """
        as_logger.debug("Scheduling sync task %s", fn)
        event = anyio.Event()
        future = Future()
        work_item = WorkItem(future=future, fn=fn, args=args, kwargs=kwargs)

        # Wake up this thread when the future is complete
        future.add_done_callback(lambda _: self._portal.call(event.set))
        self._work_queue.put(work_item)

        # Wake up the main thread
        self._wakeup.set()

        as_logger.debug("Waiting for completion...")
        # Unblock the event loop thread, wait for completion of the task
        await event.wait()

        return future.result()

    def _consume_work_queue(self):
        """
        Wait for wakeup then get work from the work queue until it is empty.
        """
        mt_logger.debug("Waiting for wakeup event...")
        self._wakeup.wait()

        while True:
            try:
                mt_logger.debug("Reading work from queue")
                work_item = self._work_queue.get_nowait()
            except queue.Empty:
                mt_logger.debug("Work queue empty!")
                break
            else:
                if work_item is not None:
                    mt_logger.debug("Running sync task %s", work_item)
                    work_item.run()
                    del work_item

        self._wakeup.clear()


@dataclasses.dataclass
class Run:
    id: uuid.UUID
    name: str


@dataclasses.dataclass
class Workflow:
    name: str
    fn: typing.Callable

    def __call__(self, **parameters):
        if inspect.iscoroutinefunction(self.fn) and not threadlocals.runtime:
            return self.fn(**parameters)
        elif threadlocals.runtime:
            return threadlocals.runtime.run_async(
                run_workflow, threadlocals.runtime, self, parameters
            )
        else:
            mt_logger.debug("Creating new runtime")
            with Runtime() as runtime:
                return runtime.run_async(run_workflow, runtime, self, parameters)


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

    if inspect.iscoroutinefunction(workflow.fn):
        result = await workflow.fn(**parameters)
    else:
        result = await runtime.run_in_main_thread(workflow.fn, **parameters)

    return result


def foo():
    print("Running foo!")
    print("In main thread?", threading.get_ident() == MAIN_THREAD)
    return 1


async def bar():
    print("Running bar!")
    print("In main thread?", threading.get_ident() == MAIN_THREAD)
    return 2


def foobar():
    return foo() + bar()


async def afoobar():
    return foo() + await bar() + 1


foo = Workflow(name="foo", fn=foo)
bar = Workflow(name="bar", fn=bar)
foobar = Workflow(name="foobar", fn=foobar)
afoobar = Workflow(name="afoobar", fn=afoobar)


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
