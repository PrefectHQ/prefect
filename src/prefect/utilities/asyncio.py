import anyio
from typing import Callable, Awaitable, Any, TypeVar
from functools import partial
from contextvars import copy_context

T = TypeVar("T")


async def run_sync_in_worker_thread(
    fn: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    call = partial(fn, *args, **kwargs)
    context = copy_context()  # Pass the context to the worker thread
    return await anyio.to_thread.run_sync(context.run, call)


def run_async_from_worker_thread(
    fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
) -> T:
    call = partial(fn, *args, **kwargs)
    return anyio.from_thread.run(call)
