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
from concurrent.futures import Future

import anyio
import anyio.abc

MAIN_THREAD = threading.get_ident()
T = typing.TypeVar("T")

logging.basicConfig(level="DEBUG")
logging.getLogger("asyncio").setLevel("INFO")

mt_logger = logging.getLogger("maint")
as_logger = logging.getLogger("async")
mt_logger.debug("Logging initialized")

threadlocals = threading.local()
threadlocals.runtime = None

current_runtime: contextvars.ContextVar["Runtime"] = contextvars.ContextVar(
    "current_runtime"
)


import asyncio


class Event(asyncio.Event):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._loop is None:
            self._loop = asyncio.get_event_loop()

    def set(self):
        self._loop.call_soon_threadsafe(super().set)

    def clear(self):
        self._loop.call_soon_threadsafe(super().clear)


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
    def __init__(self) -> None:
        self._exit_stack = contextlib.ExitStack()
        self._runtime_loop: anyio.abc.BlockingPortal = None
        self._userspace_loop: anyio.abc.BlockingPortal = None
        self._work_queue = queue.Queue()
        self._wakeup = threading.Event()
        self._thread = threading.current_thread()

    def __enter__(self):
        self._exit_stack.__enter__()
        self._runtime_loop = self._exit_stack.enter_context(
            anyio.start_blocking_portal()
        )
        self._userspace_loop = self._exit_stack.enter_context(
            anyio.start_blocking_portal()
        )
        threadlocals.runtime = self
        self._context_token = current_runtime.set(self)
        return self

    def __exit__(self, *exc_info):
        threadlocals.runtime = None
        current_runtime.reset(self._context_token)
        self._exit_stack.close()

    def run_async(
        self,
        fn: typing.Callable[..., typing.Awaitable[T]],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> T:
        mt_logger.debug("Scheduling async task %s", fn)
        # Schedule the async task on a portal thread
        future = self._runtime_loop.start_task_soon(
            functools.partial(fn, *args, **kwargs)
        )

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
        Schedule work on the main thread from the runtime thread.

        The async function must be running with `run_async`.
        """
        as_logger.debug("Scheduling sync task %s", fn)
        event = anyio.Event()
        future = Future()
        work_item = WorkItem(future=future, fn=fn, args=args, kwargs=kwargs)

        # Wake up this thread when the future is complete
        future.add_done_callback(lambda _: self._runtime_loop.call(event.set))
        self._work_queue.put(work_item)

        # Wake up the main thread
        self._wakeup.set()

        as_logger.debug("Waiting for completion...")
        # Unblock the event loop thread, wait for completion of the task
        await event.wait()

        return future.result()

    async def run_async_from_loop(
        self, fn: typing.Callable[..., T], *args: typing.Any, **kwargs: typing.Any
    ):
        """
        Schedule work on a user-space event loop from the runtime event loop.

        The user may make blocking synchronous calls and we must be careful to avoid
        blocking the runtime event loop. Even if the user's call does not perform IO,
        it may need to block to perform
        """
        future = self._userspace_loop.start_task_soon(
            functools.partial(fn, *args, **kwargs)
        )
        event = anyio.Event()
        future.add_done_callback(lambda _: self._runtime_loop.call(event.set))
        await event.wait()
        return future.result()

    def run_async_from_userspace(
        self, fn: typing.Callable[..., T], *args: typing.Any, **kwargs: typing.Any
    ):
        """ """
        future = self._runtime_loop.start_task_soon(
            functools.partial(fn, *args, **kwargs)
        )
        # event = anyio.Event()
        # future.add_done_callback(lambda _: self._runtime_loop.call(event.set))
        # await event.wait()
        # THIS BLOCKS THIS LOOP!
        # This is fine until the runtime (which we just called into) needs to schedule
        # another user-space task here. Really, this needs to be an awaitable for things
        # to work
        return future.result()

    def _consume_work_queue(self):
        """
        Wait for wakeup then get work from the work queue until it is empty.
        """
        mt_logger.debug("Waiting for wakeup event...")
        # TODO: LOOKS LIKE A RACE CONDITION HERE SOMETIMES
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

    def _get_debug_info():
        pass

    def in_sync_thread(self):
        return self._thread.ident == threading.get_ident()

    @classmethod
    def print_debug_info(cls):
        current_thread = threading.current_thread()
        # in_owner_thread = current_thread.ident == self._thread.ident
        in_main_thread = threading.main_thread().ident == current_thread.ident
        debug_info = [
            # ("In runtime owner thread?", in_owner_thread),
            ("In main thread?", in_main_thread),
        ]
        for key, result in debug_info:
            print(key, result)


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
    print(f"Entrypoint for {workflow.name!r}")
    runtime = current_runtime.get(None)
    if runtime:
        print("In sync thread?", runtime.in_sync_thread())
    if inspect.iscoroutinefunction(workflow.fn) and (
        not runtime or not runtime.in_sync_thread()
    ):
        print("Returning coroutine")
        return workflow.fn(**parameters)
    elif runtime and runtime.in_sync_thread():
        print("Running with runtime")
        return runtime.run_async(run_workflow, runtime, workflow, parameters)

    elif runtime and not runtime.in_sync_thread():
        print("Oh.. we're already in the async thread.. now what?")
        return runtime.run_async_from_userspace(
            run_workflow, runtime, workflow, parameters
        )

    else:
        mt_logger.debug("Creating new runtime")
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
    as_logger.debug("Orchestrating workflow %r", workflow.name)
    runtime = current_runtime.get()
    if inspect.iscoroutinefunction(workflow.fn):
        # Send user coroutines to another event loop that we do not "trust" in so the
        # engine event loop is never blocked
        print("Sending task to userspace loop")
        result = await runtime.run_async_from_loop(workflow.fn, **parameters)
    else:
        result = await runtime.run_in_main_thread(workflow.fn, **parameters)

    return result


def foo():
    print("Running foo!")
    Runtime.print_debug_info()
    return 1


async def bar():
    print("Running bar!")
    Runtime.print_debug_info()
    return 2


def foobar():
    print("Runing foobar")
    return foo() + bar()


async def afoobar():
    print("Running afoobar!")
    Runtime.print_debug_info()
    result = foo()
    result = foo()
    aresult = await bar()
    aresult = await bar()
    foobar()
    return result + aresult


def foofoobar():
    print("Running foofoobar")
    Runtime.print_debug_info()
    # result = foobar()
    aresult = afoobar()
    return result + aresult


async def afoofoobar():
    print("Running afoofoobar")
    Runtime.print_debug_info()
    result = foobar()
    aresult = await afoobar()
    return result + aresult


foo = Workflow(name="foo", fn=foo)
bar = Workflow(name="bar", fn=bar)
foobar = Workflow(name="foobar", fn=foobar)
afoobar = Workflow(name="afoobar", fn=afoobar)
foofoobar = Workflow(name="foofoobar", fn=foofoobar)
afoofoobar = Workflow(name="afoofoobar", fn=afoofoobar)

print("---- Sync ----")
result = foo()
print(result)

print("---- Async ----")
result = anyio.run(bar)
print(result)


print("---- Sync (parent) ----")
result = foobar()
print(result)

print("---- Async parent ----")
result = anyio.run(afoobar)
print(result)

print("---- Sync (double nested) ----")
result = foofoobar()
print(result)


# print("---- Async (double nested) ----")
# result = anyio.run(afoofoobar)
# print(result)
