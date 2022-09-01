"""
Utilities for interoperability with async functions and workers from various contexts.
"""
import ctypes
import inspect
import sys
import threading
import warnings
from contextlib import asynccontextmanager
from functools import partial, wraps
from threading import Thread
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Type, TypeVar, Union
from uuid import UUID, uuid4

import anyio
import anyio.abc
import sniffio
from typing_extensions import Literal, ParamSpec, TypeGuard

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")
Async = Literal[True]
Sync = Literal[False]
A = TypeVar("A", Async, Sync, covariant=True)

# Global references to prevent garbage collection for `add_event_loop_shutdown_callback`
EVENT_LOOP_GC_REFS = {}


def is_async_fn(
    func: Union[Callable[P, R], Callable[P, Awaitable[R]]]
) -> TypeGuard[Callable[P, Awaitable[R]]]:
    """
    This wraps `iscoroutinefunction` with a `TypeGuard` such that we can perform a
    conditional check and type checkers will narrow the expected type.

    See https://github.com/microsoft/pyright/issues/2142 for an example use
    """
    return inspect.iscoroutinefunction(func)


async def run_sync_in_worker_thread(
    __fn: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """
    Runs a sync function in a new worker thread so that the main thread's event loop
    is not blocked

    Unlike the anyio function, this defaults to a cancellable thread and does not allow
    passing arguments to the anyio function so users can pass kwargs to their function.

    Note that cancellation of threads will not result in interrupted computation, the
    thread may continue running — the outcome will just be ignored.
    """
    call = partial(__fn, *args, **kwargs)
    return await anyio.to_thread.run_sync(call, cancellable=True)


def raise_async_exception_in_thread(thread: Thread, exc_type: Type[BaseException]):
    """
    Raise an exception in a thread asynchronously.

    This will not interrupt long-running system calls like `sleep` or `wait`.
    """
    ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), ctypes.py_object(exc_type)
    )
    if ret == 0:
        raise ValueError("Thread not found.")


async def run_sync_in_interruptible_worker_thread(
    __fn: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """
    Runs a sync function in a new interruptible worker thread so that the main
    thread's event loop is not blocked

    Unlike the anyio function, this performs best-effort cancellation of the
    thread using the C API. Cancellation will not interrupt system calls like
    `sleep`.
    """

    class NotSet:
        pass

    thread: Thread = None
    result = NotSet

    def capture_worker_thread_and_result():
        # Captures the worker thread that AnyIO is using to execute the function so
        # the main thread can perform actions on it
        nonlocal thread, result
        try:
            thread = threading.current_thread()
            result = __fn(*args, **kwargs)
        except BaseException as exc:
            result = exc
            raise

    async def send_interrupt_to_thread():
        # This task waits until the result is returned from the thread, if cancellation
        # occurs during that time, we will raise the exception in the thread as well
        try:
            while result is NotSet:
                await anyio.sleep(0)
        except anyio.get_cancelled_exc_class():
            # NOTE: We could send a SIGINT here which allow us to interrupt system
            # calls but the interrupt bubbles from the child thread into the main thread
            # and there is not a clear way to prevent it.
            raise_async_exception_in_thread(thread, anyio.get_cancelled_exc_class())
            raise

    async with anyio.create_task_group() as tg:
        tg.start_soon(send_interrupt_to_thread)
        tg.start_soon(
            partial(
                anyio.to_thread.run_sync,
                capture_worker_thread_and_result,
                cancellable=True,
            )
        )

    assert result is not NotSet
    return result


def run_async_from_worker_thread(
    __fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
) -> T:
    """
    Runs an async function in the main thread's event loop, blocking the worker
    thread until completion
    """
    call = partial(__fn, *args, **kwargs)
    return anyio.from_thread.run(call)


def run_async_in_new_loop(__fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any):
    return anyio.run(partial(__fn, *args, **kwargs))


def in_async_worker_thread() -> bool:
    try:
        anyio.from_thread.threadlocals.current_async_module
    except AttributeError:
        return False
    else:
        return True


def in_async_main_thread() -> bool:
    try:
        sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        return False
    else:
        # We could be in a worker thread, not the main thread
        return not in_async_worker_thread()


def sync_compatible(async_fn: T) -> T:
    """
    Converts an async function into a dual async and sync function.

    When the returned function is called, we will attempt to determine the best way
    to enter the async function.

    - If in a thread with a running event loop, we will return the coroutine for the
        caller to await. This is normal async behavior.
    - If in a blocking worker thread with access to an event loop in another thread, we
        will submit the async method to the event loop.
    - If we cannot find an event loop, we will create a new one and run the async method
        then tear down the loop.
    """
    # TODO: This is breaking type hints on the callable... mypy is behind the curve
    #       on argument annotations. We can still fix this for editors though.
    if not inspect.iscoroutinefunction(async_fn):
        raise TypeError("The decorated function must be async.")

    @wraps(async_fn)
    def wrapper(*args, **kwargs):
        if in_async_main_thread():
            caller_frame = sys._getframe(1)
            caller_module = caller_frame.f_globals.get("__name__", "unknown")
            caller_async = caller_frame.f_code.co_flags & inspect.CO_COROUTINE
            if caller_async or any(
                # Add exceptions for the internals anyio/asyncio which can run
                # coroutines from synchronous functions
                caller_module.startswith(f"{module}.")
                for module in ["asyncio", "anyio"]
            ):
                # In the main async context; return the coro for them to await
                return async_fn(*args, **kwargs)
            else:
                # In the main thread but call was made from a sync method
                raise RuntimeError(
                    "A 'sync_compatible' method was called from a context that was "
                    "previously async but is now sync. The sync call must be changed "
                    "to run in a worker thread to support sending the coroutine for "
                    f"{async_fn.__name__!r} to the main thread."
                )

        elif in_async_worker_thread():
            # In a sync context but we can access the event loop thread; send the async
            # call to the parent
            return run_async_from_worker_thread(async_fn, *args, **kwargs)
        else:
            # In a sync context and there is no event loop; just create an event loop
            # to run the async code then tear it down
            return run_async_in_new_loop(async_fn, *args, **kwargs)

    wrapper.aio = async_fn
    return wrapper


@asynccontextmanager
async def asyncnullcontext():
    yield


def sync(__async_fn: Callable[P, Awaitable[T]], *args: P.args, **kwargs: P.kwargs) -> T:
    """
    Call an async function from a synchronous context. Block until completion.

    If in an asynchronous context, we will run the code in a separate loop instead of
    failing but a warning will be displayed since this is not recommended.
    """
    if in_async_main_thread():
        warnings.warn(
            "`sync` called from an asynchronous context; "
            "you should `await` the async function directly instead."
        )
        with anyio.start_blocking_portal() as portal:
            return portal.call(partial(__async_fn, *args, **kwargs))
    elif in_async_worker_thread():
        # In a sync context but we can access the event loop thread; send the async
        # call to the parent
        return run_async_from_worker_thread(__async_fn, *args, **kwargs)
    else:
        # In a sync context and there is no event loop; just create an event loop
        # to run the async code then tear it down
        return run_async_in_new_loop(__async_fn, *args, **kwargs)


async def add_event_loop_shutdown_callback(coroutine_fn: Callable[[], Awaitable]):
    """
    Adds a callback to the given callable on event loop closure. The callable must be
    a coroutine function. It will be awaited when the current event loop is shutting
    down.

    Requires use of `asyncio.run()` which waits for async generator shutdown by
    default or explicit call of `asyncio.shutdown_asyncgens()`. If the application
    is entered with `asyncio.run_until_complete()` and the user calls
    `asyncio.close()` without the generator shutdown call, this will not trigger
    callbacks.

    asyncio does not provided _any_ other way to clean up a resource when the event
    loop is about to close.
    """

    async def on_shutdown(key):
        try:
            yield
        except GeneratorExit:
            await coroutine_fn()
            # Remove self from the garbage collection set
            EVENT_LOOP_GC_REFS.pop(key)

    # Create the iterator and store it in a global variable so it is not garbage
    # collected. If the iterator is garbage collected before the event loop closes, the
    # callback will not run. Since this function does not know the scope of the event
    # loop that is calling it, a reference with global scope is necessary to ensure
    # garbage collection does not occur until after event loop closure.
    key = id(on_shutdown)
    EVENT_LOOP_GC_REFS[key] = on_shutdown(key)

    # Begin iterating so it will be cleaned up as an incomplete generator
    await EVENT_LOOP_GC_REFS[key].__anext__()


class GatherIncomplete(RuntimeError):
    """Used to indicate retrieving gather results before completion"""


class GatherTaskGroup(anyio.abc.TaskGroup):
    """
    A task group that gathers results.

    AnyIO does not include support `gather`. This class extends the `TaskGroup`
    interface to allow simple gathering.

    See https://github.com/agronholm/anyio/issues/100

    This class should be instantiated with `create_gather_task_group`.
    """

    def __init__(self, task_group: anyio.abc.TaskGroup):
        self._results: Dict[UUID, Any] = {}
        # The concrete task group implementation to use
        self._task_group: anyio.abc.TaskGroup = task_group

    async def _run_and_store(self, key, fn, args):
        self._results[key] = await fn(*args)

    def start_soon(self, fn, *args) -> UUID:
        key = uuid4()
        # Put a placeholder in-case the result is retrieved earlier
        self._results[key] = GatherIncomplete
        self._task_group.start_soon(self._run_and_store, key, fn, args)
        return key

    async def start(self, fn, *args):
        """
        Since `start` returns the result of `task_status.started()` but here we must
        return the key instead, we just won't support this method for now.
        """
        raise RuntimeError("`GatherTaskGroup` does not support `start`.")

    def get_result(self, key: UUID) -> Any:
        result = self._results[key]
        if result is GatherIncomplete:
            raise GatherIncomplete(
                "Task is not complete. "
                "Results should not be retrieved until the task group exits."
            )
        return result

    async def __aenter__(self):
        await self._task_group.__aenter__()
        return self

    async def __aexit__(self, *tb):
        try:
            retval = await self._task_group.__aexit__(*tb)
            return retval
        finally:
            del self._task_group


def create_gather_task_group() -> GatherTaskGroup:
    """Create a new task group that gathers results"""
    # This function matches the AnyIO API which uses callables since the concrete
    # task group class depends on the async library being used and cannot be
    # determined until runtime
    return GatherTaskGroup(anyio.create_task_group())


async def gather(*calls: Callable[[], Coroutine[Any, Any, T]]) -> List[T]:
    """
    Run calls concurrently and gather their results.

    Unlike `asyncio.gather` this expects to receieve _callables_ not _coroutines_.
    This matches `anyio` semantics.
    """
    keys = []
    async with create_gather_task_group() as tg:
        for call in calls:
            keys.append(tg.start_soon(call))
    return [tg.get_result(key) for key in keys]
