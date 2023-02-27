import asyncio
from typing import Callable, TypeVar

from typing_extensions import ParamSpec

from prefect._internal.concurrency.runtime import get_runtime_thread
from prefect._internal.concurrency.supervisors import AsyncSupervisor, get_supervisor

P = ParamSpec("P")
T = TypeVar("T")


def call_soon_in_runtime_thread(
    __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> AsyncSupervisor[T]:
    """
    Schedule a coroutine function in the runtime thread.

    Returns a supervisor.
    """
    current_supervisor = get_supervisor()
    runtime = get_runtime_thread()

    if (
        current_supervisor is None
        or current_supervisor.owner_thread.ident != runtime.ident
    ):
        submit_fn = runtime.submit_to_loop
    else:
        submit_fn = current_supervisor.send_call_to_supervisor

    supervisor = AsyncSupervisor(submit_fn=submit_fn)
    supervisor.submit(__fn, *args, **kwargs)
    return supervisor


def call_soon_in_worker_thread(
    __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> AsyncSupervisor[T]:
    """
    Schedule a function in a worker thread.

    Returns a supervisor.
    """
    runtime = get_runtime_thread()
    supervisor = AsyncSupervisor(runtime.submit_to_worker_thread)
    supervisor.submit(__fn, *args, **kwargs)
    return supervisor


def call_soon_in_supervising_thread(
    __fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> asyncio.Future:  # [T]
    """
    Call a function in the supervising thread.

    Must be used from a call scheduled by `call_soon_in_worker_thread` or
    `call_soon_in_runtime_thread` or there will not be a supervisor.

    Note the future returned by this is an `asyncio.Future` and calling `.result()`
    before awaiting the future will result in an error.

    Returns a future.
    """
    current_future = get_supervisor()
    if current_future is None:
        raise RuntimeError("No supervisor found.")

    future = current_future.send_call_to_supervisor(__fn, *args, **kwargs)
    return asyncio.wrap_future(future)
