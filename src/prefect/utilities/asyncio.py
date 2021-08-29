from contextvars import copy_context
from functools import partial
from typing import Any, Awaitable, Callable, TypeVar

import anyio

T = TypeVar("T")


async def run_sync_in_worker_thread(
    fn: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """
    Runs a sync function in a new worker thread so that the main thread's event loop
    is not blocked

    Unlike the anyio function, this ensures that context variables are copied into the
    worker thread.
    """
    call = partial(fn, *args, **kwargs)
    context = copy_context()  # Pass the context to the worker thread
    return await anyio.to_thread.run_sync(context.run, call)


def run_async_from_worker_thread(
    fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
) -> T:
    """
    Runs an async function in the main thread's event loop, blocking the worker
    thread until completion
    """
    call = partial(fn, *args, **kwargs)
    return anyio.from_thread.run(call)


def is_in_async_worker_thread() -> bool:

    try:
        anyio.from_thread.threadlocals.current_async_module
        return True
    except AttributeError:
        return False
