"""
Utilities for interoperability with async functions and workers from various contexts.
"""

import asyncio
import inspect
import threading
import warnings
from collections.abc import AsyncGenerator, Awaitable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar
from functools import partial, wraps
from logging import Logger
from typing import TYPE_CHECKING, Any, Callable, NoReturn, Optional, Union, overload
from uuid import UUID, uuid4

import anyio
import anyio.abc
import anyio.from_thread
import anyio.to_thread
import sniffio
from typing_extensions import (
    Literal,
    ParamSpec,
    Self,
    TypeAlias,
    TypeGuard,
    TypeVar,
    TypeVarTuple,
    Unpack,
)

from prefect._internal.concurrency.api import cast_to_call, from_sync
from prefect._internal.concurrency.threads import (
    get_run_sync_loop,
    in_run_sync_loop,
)
from prefect.logging import get_logger

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)
F = TypeVar("F", bound=Callable[..., Any])
Async = Literal[True]
Sync = Literal[False]
A = TypeVar("A", Async, Sync, covariant=True)
PosArgsT = TypeVarTuple("PosArgsT")

_SyncOrAsyncCallable: TypeAlias = Callable[P, Union[R, Awaitable[R]]]

# Global references to prevent garbage collection for `add_event_loop_shutdown_callback`
EVENT_LOOP_GC_REFS: dict[int, AsyncGenerator[None, Any]] = {}


RUNNING_IN_RUN_SYNC_LOOP_FLAG = ContextVar("running_in_run_sync_loop", default=False)
RUNNING_ASYNC_FLAG = ContextVar("run_async", default=False)
BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()
background_task_lock: threading.Lock = threading.Lock()

# Thread-local storage to keep track of worker thread state
_thread_local = threading.local()

logger: Logger = get_logger()


_prefect_thread_limiter: Optional[anyio.CapacityLimiter] = None


def get_thread_limiter() -> anyio.CapacityLimiter:
    global _prefect_thread_limiter

    if _prefect_thread_limiter is None:
        _prefect_thread_limiter = anyio.CapacityLimiter(250)

    return _prefect_thread_limiter


def is_async_fn(
    func: _SyncOrAsyncCallable[P, R],
) -> TypeGuard[Callable[P, Coroutine[Any, Any, Any]]]:
    """
    Returns `True` if a function returns a coroutine.

    See https://github.com/microsoft/pyright/issues/2142 for an example use
    """
    func = inspect.unwrap(func)
    return asyncio.iscoroutinefunction(func)


def is_async_gen_fn(
    func: Callable[P, Any],
) -> TypeGuard[Callable[P, AsyncGenerator[Any, Any]]]:
    """
    Returns `True` if a function is an async generator.
    """
    func = inspect.unwrap(func)
    return inspect.isasyncgenfunction(func)


def create_task(coroutine: Coroutine[Any, Any, R]) -> asyncio.Task[R]:
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


@overload
def run_coro_as_sync(
    coroutine: Coroutine[Any, Any, R],
    *,
    force_new_thread: bool = ...,
    wait_for_result: Literal[True] = ...,
) -> R: ...


@overload
def run_coro_as_sync(
    coroutine: Coroutine[Any, Any, R],
    *,
    force_new_thread: bool = ...,
    wait_for_result: Literal[False] = False,
) -> R: ...


def run_coro_as_sync(
    coroutine: Coroutine[Any, Any, R],
    *,
    force_new_thread: bool = False,
    wait_for_result: bool = True,
) -> Optional[R]:
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

    async def coroutine_wrapper() -> Optional[R]:
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
        result = from_sync.call_in_new_thread(coroutine_wrapper)
        return result

    # otherwise, we can run the coroutine in the run_sync loop
    # and wait for the result
    else:
        call = cast_to_call(coroutine_wrapper)
        runner = get_run_sync_loop()
        runner.submit(call)
        try:
            return call.result()
        except KeyboardInterrupt:
            call.cancel()

            logger.debug("Coroutine cancelled due to KeyboardInterrupt.")
            raise


async def run_sync_in_worker_thread(
    __fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs
) -> R:
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


def call_with_mark(call: Callable[..., R]) -> R:
    mark_as_worker_thread()
    return call()


def run_async_from_worker_thread(
    __fn: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
) -> R:
    """
    Runs an async function in the main thread's event loop, blocking the worker
    thread until completion
    """
    call = partial(__fn, *args, **kwargs)
    return anyio.from_thread.run(call)


def run_async_in_new_loop(
    __fn: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs
) -> R:
    return anyio.run(partial(__fn, *args, **kwargs))


def mark_as_worker_thread() -> None:
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


def sync_compatible(
    async_fn: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Union[R, Coroutine[Any, Any, R]]]:
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

    Note: Type checkers will infer functions decorated with `@sync_compatible` are synchronous. If
    you want to use the decorated function in an async context, you will need to ignore the types
    and "cast" the return type to a coroutine. For example:
    ```
    python result: Coroutine = sync_compatible(my_async_function)(arg1, arg2) # type: ignore
    ```
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
        elif RUNNING_ASYNC_FLAG.get() or is_async:
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


@overload
def asyncnullcontext(
    value: None = None, *args: Any, **kwargs: Any
) -> AbstractAsyncContextManager[None, None]: ...


@overload
def asyncnullcontext(
    value: R, *args: Any, **kwargs: Any
) -> AbstractAsyncContextManager[R, None]: ...


@asynccontextmanager
async def asyncnullcontext(
    value: Optional[R] = None, *args: Any, **kwargs: Any
) -> AsyncGenerator[Any, Optional[R]]:
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
        with anyio.from_thread.start_blocking_portal() as portal:
            return portal.call(partial(__async_fn, *args, **kwargs))
    elif in_async_worker_thread():
        # In a sync context but we can access the event loop thread; send the async
        # call to the parent
        return run_async_from_worker_thread(__async_fn, *args, **kwargs)
    else:
        # In a sync context and there is no event loop; just create an event loop
        # to run the async code then tear it down
        return run_async_in_new_loop(__async_fn, *args, **kwargs)


async def add_event_loop_shutdown_callback(
    coroutine_fn: Callable[[], Awaitable[Any]],
) -> None:
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

    async def on_shutdown(key: int) -> AsyncGenerator[None, Any]:
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

    AnyIO does not include `gather` support. This class extends the `TaskGroup`
    interface to allow simple gathering.

    See https://github.com/agronholm/anyio/issues/100

    This class should be instantiated with `create_gather_task_group`.
    """

    def __init__(self, task_group: anyio.abc.TaskGroup):
        self._results: dict[UUID, Any] = {}
        # The concrete task group implementation to use
        self._task_group: anyio.abc.TaskGroup = task_group

    async def _run_and_store(
        self,
        key: UUID,
        fn: Callable[[Unpack[PosArgsT]], Awaitable[Any]],
        *args: Unpack[PosArgsT],
    ) -> None:
        self._results[key] = await fn(*args)

    def start_soon(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        func: Callable[[Unpack[PosArgsT]], Awaitable[Any]],
        *args: Unpack[PosArgsT],
        name: object = None,
    ) -> UUID:
        key = uuid4()
        # Put a placeholder in-case the result is retrieved earlier
        self._results[key] = GatherIncomplete
        self._task_group.start_soon(self._run_and_store, key, func, *args, name=name)
        return key

    async def start(self, func: object, *args: object, name: object = None) -> NoReturn:
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

    async def __aenter__(self) -> Self:
        await self._task_group.__aenter__()
        return self

    async def __aexit__(self, *tb: Any) -> Optional[bool]:
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


async def gather(*calls: Callable[[], Coroutine[Any, Any, T]]) -> list[T]:
    """
    Run calls concurrently and gather their results.

    Unlike `asyncio.gather` this expects to receive _callables_ not _coroutines_.
    This matches `anyio` semantics.
    """
    keys: list[UUID] = []
    async with create_gather_task_group() as tg:
        for call in calls:
            keys.append(tg.start_soon(call))
    return [tg.get_result(key) for key in keys]


class LazySemaphore:
    def __init__(self, initial_value_func: Callable[[], int]) -> None:
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._initial_value_func = initial_value_func

    async def __aenter__(self) -> asyncio.Semaphore:
        self._initialize_semaphore()
        if TYPE_CHECKING:
            assert self._semaphore is not None
        await self._semaphore.__aenter__()
        return self._semaphore

    async def __aexit__(self, *args: Any) -> None:
        if TYPE_CHECKING:
            assert self._semaphore is not None
        await self._semaphore.__aexit__(*args)

    def _initialize_semaphore(self) -> None:
        if self._semaphore is None:
            initial_value = self._initial_value_func()
            self._semaphore = asyncio.Semaphore(initial_value)
