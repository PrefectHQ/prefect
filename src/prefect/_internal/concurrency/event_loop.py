"""
Thread-safe utilities for working with asynchronous event loops.
"""

import asyncio
import concurrent.futures
import functools
from typing import Callable, Optional, TypeVar

from typing_extensions import ParamSpec

P = ParamSpec("P")
T = TypeVar("T")


def get_running_loop() -> Optional[asyncio.BaseEventLoop]:
    """
    Get the current running loop.

    Returns `None` if there is no running loop.
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def call_in_loop(
    __loop: asyncio.AbstractEventLoop,
    __fn: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs
) -> T:
    """
    Run a synchronous call in event loop's thread from another thread.

    This function is blocking and not safe to call from an asynchronous context.

    Returns the result of the call.
    """
    future = call_soon_in_loop(__loop, __fn, *args, **kwargs)
    return future.result()


def call_soon_in_loop(
    __loop: asyncio.AbstractEventLoop,
    __fn: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs
) -> concurrent.futures.Future:
    """
    Run a synchronous call in an event loop's thread from another thread.

    This function is non-blocking and safe to call from an asynchronous context.

    Returns a future that can be used to retrieve the result of the call.
    """
    future = concurrent.futures.Future()

    @functools.wraps(__fn)
    def wrapper() -> None:
        try:
            result = __fn(*args, **kwargs)
        except BaseException as exc:
            future.set_exception(exc)
            if not isinstance(exc, Exception):
                raise
        else:
            future.set_result(result)

    # `call_soon...` returns a `Handle` object which doesn't provide access to the
    # result of the call. We wrap the call with a future to facilitate retrieval.
    if __loop is get_running_loop():
        __loop.call_soon(wrapper)
    else:
        __loop.call_soon_threadsafe(wrapper)

    return future
