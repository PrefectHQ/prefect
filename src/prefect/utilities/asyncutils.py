"""
Utilities for interoperability with async functions and workers from various contexts.
"""

import asyncio
import inspect
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from contextvars import ContextVar, copy_context
from functools import partial, wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID, uuid4

import anyio
import anyio.abc
import sniffio
from typing_extensions import Literal, ParamSpec, TypeGuard

from prefect.logging import get_logger

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")
Async = Literal[True]
Sync = Literal[False]
A = TypeVar("A", Async, Sync, covariant=True)

# Global references to prevent garbage collection for `add_event_loop_shutdown_callback`
EVENT_LOOP_GC_REFS = {}

PREFECT_THREAD_LIMITER: Optional[anyio.CapacityLimiter] = None

RUN_ASYNC_FLAG = ContextVar("run_async", default=False)

logger = get_logger()


def get_thread_limiter():
    global PREFECT_THREAD_LIMITER

    if PREFECT_THREAD_LIMITER is None:
        PREFECT_THREAD_LIMITER = anyio.CapacityLimiter(250)

    return PREFECT_THREAD_LIMITER


def is_async_fn(
    func: Union[Callable[P, R], Callable[P, Awaitable[R]]],
) -> TypeGuard[Callable[P, Awaitable[R]]]:
    """
    Returns `True` if a function returns a coroutine.

    See https://github.com/microsoft/pyright/issues/2142 for an example use
    """
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__

    return inspect.iscoroutinefunction(func)


def is_async_gen_fn(func):
    """
    Returns `True` if a function is an async generator.
    """
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__

    return inspect.isasyncgenfunction(func)


def run_sync(coroutine: Coroutine[Any, Any, T]) -> T:
    """
    Runs a coroutine from a synchronous context. A thread will be spawned
    to run the event loop if necessary, which allows coroutines to run in
    environments like Jupyter notebooks where the event loop runs on the main
    thread.

    Args:
        coroutine: The coroutine to run.

    Returns:
        The return value of the coroutine.

    Example:
        Basic usage:
        ```python
        async def my_async_function(x: int) -> int:
            return x + 1

        run_sync(my_async_function(1))
        ```
    """

    # ensure context variables are properly copied to the async frame
    async def context_local_wrapper():
        """
        Wrapper that is submitted using copy_context().run to ensure
        the RUN_ASYNC_FLAG mutations are tightly scoped to this coroutine's frame.
        """
        token = RUN_ASYNC_FLAG.set(True)
        try:
            result = await coroutine
        finally:
            RUN_ASYNC_FLAG.reset(token)
        return result

    context = copy_context()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor() as executor:
            future = executor.submit(context.run, asyncio.run, context_local_wrapper())
            result = cast(T, future.result())
    else:
        result = context.run(asyncio.run, context_local_wrapper())
    return result


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
    return await anyio.to_thread.run_sync(
        call, cancellable=True, limiter=get_thread_limiter()
    )


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


def sync_compatible(async_fn: T, force_sync: bool = False) -> T:
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

    @wraps(async_fn)
    def coroutine_wrapper(*args, **kwargs):
        from prefect.context import MissingContextError, get_run_context
        from prefect.settings import (
            PREFECT_EXPERIMENTAL_DISABLE_SYNC_COMPAT,
        )

        if PREFECT_EXPERIMENTAL_DISABLE_SYNC_COMPAT:
            return async_fn(*args, **kwargs)

        is_async = True
        try:
            run_ctx = get_run_context()
            parent_obj = getattr(run_ctx, "task", None)
            if not parent_obj:
                parent_obj = getattr(run_ctx, "flow", None)
            is_async = getattr(parent_obj, "isasync", True)
        except MissingContextError:
            pass

        async def ctx_call():
            """
            Wrapper that is submitted using copy_context().run to ensure
            mutations of RUN_ASYNC_FLAG are tightly scoped to this coroutine's frame.
            """
            token = RUN_ASYNC_FLAG.set(True)
            try:
                result = await async_fn(*args, **kwargs)
            finally:
                RUN_ASYNC_FLAG.reset(token)
            return result

        if force_sync:
            return run_sync(ctx_call())
        elif RUN_ASYNC_FLAG.get() or is_async:
            context = copy_context()
            return context.run(ctx_call)
        else:
            return run_sync(ctx_call())

    # TODO: This is breaking type hints on the callable... mypy is behind the curve
    #       on argument annotations. We can still fix this for editors though.
    if is_async_fn(async_fn):
        wrapper = coroutine_wrapper
    elif is_async_gen_fn(async_fn):
        raise ValueError("Async generators cannot yet be marked as `sync_compatible`")
    else:
        raise TypeError("The decorated function must be async.")

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
        # It appears that EVENT_LOOP_GC_REFS is somehow being garbage collected early.
        # We hold a reference to it so as to preserve it, at least for the lifetime of
        # this coroutine. See the issue below for the initial report/discussion:
        # https://github.com/PrefectHQ/prefect/issues/7709#issuecomment-1560021109
        _ = EVENT_LOOP_GC_REFS
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
    try:
        await EVENT_LOOP_GC_REFS[key].__anext__()
    # There is a poorly understood edge case we've seen in CI where the key is
    # removed from the dict before we begin generator iteration.
    except KeyError:
        logger.warning("The event loop shutdown callback was not properly registered. ")
        pass


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

    Unlike `asyncio.gather` this expects to receive _callables_ not _coroutines_.
    This matches `anyio` semantics.
    """
    keys = []
    async with create_gather_task_group() as tg:
        for call in calls:
            keys.append(tg.start_soon(call))
    return [tg.get_result(key) for key in keys]


class LazySemaphore:
    def __init__(self, initial_value_func):
        self._semaphore = None
        self._initial_value_func = initial_value_func

    async def __aenter__(self):
        self._initialize_semaphore()
        await self._semaphore.__aenter__()
        return self._semaphore

    async def __aexit__(self, exc_type, exc, tb):
        await self._semaphore.__aexit__(exc_type, exc, tb)

    def _initialize_semaphore(self):
        if self._semaphore is None:
            initial_value = self._initial_value_func()
            self._semaphore = asyncio.Semaphore(initial_value)
