"""
Utilities for interoperability with async functions and workers from various contexts.
"""

import asyncio
import inspect
import threading
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
    overload,
)
from uuid import UUID, uuid4

import anyio
import anyio.abc
import anyio.from_thread
import anyio.to_thread
import sniffio
from typing_extensions import Literal, ParamSpec, TypeGuard

from prefect._internal.concurrency.api import _cast_to_call, from_sync
from prefect._internal.concurrency.threads import (
    get_run_sync_loop,
    in_run_sync_loop,
)
from prefect.logging import get_logger

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")
F = TypeVar("F", bound=Callable[..., Any])
Async = Literal[True]
Sync = Literal[False]
A = TypeVar("A", Async, Sync, covariant=True)

# Global references to prevent garbage collection for `add_event_loop_shutdown_callback`
EVENT_LOOP_GC_REFS = {}

PREFECT_THREAD_LIMITER: Optional[anyio.CapacityLimiter] = None

RUNNING_IN_RUN_SYNC_LOOP_FLAG = ContextVar("running_in_run_sync_loop", default=False)
RUNNING_ASYNC_FLAG = ContextVar("run_async", default=False)
BACKGROUND_TASKS: set[asyncio.Task] = set()
background_task_lock = threading.Lock()

# Thread-local storage to keep track of worker thread state
_thread_local = threading.local()

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


def create_task(coroutine: Coroutine) -> asyncio.Task:
    """
    Replacement for asyncio.create_task that will ensure that tasks aren't
    garbage collected before they complete. Allows for "fire and forget"
    behavior in which tasks can be created and the application can move on.
    Tasks can also be awaited normally.

    See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
    for details (and essentially this implementation)
    """

    task = asyncio.create_task(coroutine)

    # Add task to the set. This creates a strong reference.
    # Take a lock because this might be done from multiple threads.
    with background_task_lock:
        BACKGROUND_TASKS.add(task)

    # To prevent keeping references to finished tasks forever,
    # make each task remove its own reference from the set after
    # completion:
    task.add_done_callback(BACKGROUND_TASKS.discard)

    return task


def _run_sync_in_new_thread(coroutine: Coroutine[Any, Any, T]) -> T:
    """
    Note: this is an OLD implementation of `run_coro_as_sync` which liberally created
    new threads and new loops. This works, but prevents sharing any objects
    across coroutines, in particular httpx clients, which are very expensive to
    instantiate.

    This is here for historical purposes and can be removed if/when it is no
    longer needed for reference.

    ---

    Runs a coroutine from a synchronous context. A thread will be spawned to run
    the event loop if necessary, which allows coroutines to run in environments
    like Jupyter notebooks where the event loop runs on the main thread.

    Args:
        coroutine: The coroutine to run.

    Returns:
        The return value of the coroutine.

    Example:
        Basic usage: ```python async def my_async_function(x: int) -> int:
            return x + 1

        run_sync(my_async_function(1)) ```
    """

    # ensure context variables are properly copied to the async frame
    async def context_local_wrapper():
        """
        Wrapper that is submitted using copy_context().run to ensure
        the RUNNING_ASYNC_FLAG mutations are tightly scoped to this coroutine's frame.
        """
        token = RUNNING_ASYNC_FLAG.set(True)
        try:
            result = await coroutine
        finally:
            RUNNING_ASYNC_FLAG.reset(token)
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


def run_coro_as_sync(
    coroutine: Awaitable[R],
    force_new_thread: bool = False,
    wait_for_result: bool = True,
) -> Union[R, None]:
    """
    Runs a coroutine from a synchronous context, as if it were a synchronous
    function.

    The coroutine is scheduled to run in the "run sync" event loop, which is
    running in its own thread and is started the first time it is needed. This
    allows us to share objects like async httpx clients among all coroutines
    running in the loop.

    If run_sync is called from within the run_sync loop, it will run the
    coroutine in a new thread, because otherwise a deadlock would occur. Note
    that this behavior should not appear anywhere in the Prefect codebase or in
    user code.

    Args:
        coroutine (Awaitable): The coroutine to be run as a synchronous function.
        force_new_thread (bool, optional): If True, the coroutine will always be run in a new thread.
            Defaults to False.
        wait_for_result (bool, optional): If True, the function will wait for the coroutine to complete
            and return the result. If False, the function will submit the coroutine to the "run sync"
            event loop and return immediately, where it will eventually be run. Defaults to True.

    Returns:
        The result of the coroutine if wait_for_result is True, otherwise None.
    """

    async def coroutine_wrapper() -> Union[R, None]:
        """
        Set flags so that children (and grandchildren...) of this task know they are running in a new
        thread and do not try to run on the run_sync thread, which would cause a
        deadlock.
        """
        token1 = RUNNING_IN_RUN_SYNC_LOOP_FLAG.set(True)
        token2 = RUNNING_ASYNC_FLAG.set(True)
        try:
            # use `asyncio.create_task` because it copies context variables automatically
            task = create_task(coroutine)
            if wait_for_result:
                return await task
        finally:
            RUNNING_IN_RUN_SYNC_LOOP_FLAG.reset(token1)
            RUNNING_ASYNC_FLAG.reset(token2)

    # if we are already in the run_sync loop, or a descendent of a coroutine
    # that is running in the run_sync loop, we need to run this coroutine in a
    # new thread
    if in_run_sync_loop() or RUNNING_IN_RUN_SYNC_LOOP_FLAG.get() or force_new_thread:
        return from_sync.call_in_new_thread(coroutine_wrapper)

    # otherwise, we can run the coroutine in the run_sync loop
    # and wait for the result
    else:
        call = _cast_to_call(coroutine_wrapper)
        runner = get_run_sync_loop()
        runner.submit(call)
        try:
            return call.result()
        except KeyboardInterrupt:
            call.cancel()

            logger.debug("Coroutine cancelled due to KeyboardInterrupt.")
            raise


async def run_sync_in_worker_thread(
    __fn: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """
    Runs a sync function in a new worker thread so that the main thread's event loop
    is not blocked.

    Unlike the anyio function, this defaults to a cancellable thread and does not allow
    passing arguments to the anyio function so users can pass kwargs to their function.

    Note that cancellation of threads will not result in interrupted computation, the
    thread may continue running — the outcome will just be ignored.
    """
    # When running a sync function in a worker thread, we set this flag so that
    # any root sync compatible functions will run as sync functions
    token = RUNNING_ASYNC_FLAG.set(False)
    try:
        call = partial(__fn, *args, **kwargs)
        result = await anyio.to_thread.run_sync(
            call_with_mark, call, abandon_on_cancel=True, limiter=get_thread_limiter()
        )
        return result
    finally:
        RUNNING_ASYNC_FLAG.reset(token)


def call_with_mark(call):
    mark_as_worker_thread()
    return call()


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


def mark_as_worker_thread():
    _thread_local.is_worker_thread = True


def in_async_worker_thread() -> bool:
    return getattr(_thread_local, "is_worker_thread", False)


def in_async_main_thread() -> bool:
    try:
        sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        return False
    else:
        # We could be in a worker thread, not the main thread
        return not in_async_worker_thread()


@overload
def sync_compatible(
    async_fn: Callable[..., Coroutine[Any, Any, R]],
) -> Callable[..., R]:
    ...


@overload
def sync_compatible(
    async_fn: Callable[..., Coroutine[Any, Any, R]],
) -> Callable[..., Coroutine[Any, Any, R]]:
    ...


def sync_compatible(
    async_fn: Callable[..., Coroutine[Any, Any, R]],
) -> Callable[..., Union[R, Coroutine[Any, Any, R]]]:
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
    def coroutine_wrapper(
        *args: Any, _sync: Optional[bool] = None, **kwargs: Any
    ) -> Union[R, Coroutine[Any, Any, R]]:
        from prefect.context import MissingContextError, get_run_context

        if _sync is False:
            return async_fn(*args, **kwargs)

        is_async = True

        # if _sync is set, we do as we're told
        # otherwise, we make some determinations
        if _sync is None:
            try:
                run_ctx = get_run_context()
                parent_obj = getattr(run_ctx, "task", None)
                if not parent_obj:
                    parent_obj = getattr(run_ctx, "flow", None)
                is_async = getattr(parent_obj, "isasync", True)
            except MissingContextError:
                # not in an execution context, make best effort to
                # decide whether to syncify
                try:
                    asyncio.get_running_loop()
                    is_async = True
                except RuntimeError:
                    is_async = False

        async def ctx_call():
            """
            Wrapper that is submitted using copy_context().run to ensure
            mutations of RUNNING_ASYNC_FLAG are tightly scoped to this coroutine's frame.
            """
            token = RUNNING_ASYNC_FLAG.set(True)
            try:
                result = await async_fn(*args, **kwargs)
            finally:
                RUNNING_ASYNC_FLAG.reset(token)
            return result

        if _sync is True:
            return run_coro_as_sync(ctx_call())
        elif _sync is False or RUNNING_ASYNC_FLAG.get() or is_async:
            return ctx_call()
        else:
            return run_coro_as_sync(ctx_call())

    if is_async_fn(async_fn):
        wrapper = coroutine_wrapper
    elif is_async_gen_fn(async_fn):
        raise ValueError("Async generators cannot yet be marked as `sync_compatible`")
    else:
        raise TypeError("The decorated function must be async.")

    wrapper.aio = async_fn  # type: ignore
    return wrapper


@asynccontextmanager
async def asyncnullcontext(value=None, *args, **kwargs):
    yield value


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
