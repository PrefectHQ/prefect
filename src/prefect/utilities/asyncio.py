"""
Utilities for interoperability with async functions and workers from various contexts.
"""
import inspect
import warnings
from contextvars import copy_context
from functools import partial, wraps
from typing import Any, Awaitable, Callable, TypeVar, Union
from typing_extensions import Literal
from contextlib import asynccontextmanager

import anyio
import sniffio
from typing_extensions import ParamSpec, TypeGuard

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")
Async = Literal[True]
Sync = Literal[False]
A = TypeVar("A", Async, Sync, covariant=True)


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

    Unlike the anyio function, this ensures that context variables are copied into the
    worker thread.
    """
    call = partial(__fn, *args, **kwargs)
    context = copy_context()  # Pass the context to the worker thread
    return await anyio.to_thread.run_sync(context.run, call, cancellable=True)


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
            # In the main async context; return the coro for them to await
            return async_fn(*args, **kwargs)
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
