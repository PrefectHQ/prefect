import concurrent.futures
import threading

from prefect._internal.concurrency.futures import (
    SyncWatchingFuture,
    get_current_future,
    set_current_future,
)
from prefect._internal.concurrency.runtime import get_runtime_thread


def call_soon_in_runtime_thread(__fn, *args, **kwargs) -> SyncWatchingFuture:
    """
    Schedule a coroutine function in the runtime thread.

    Returns a watching future.
    """
    current_future = get_current_future()
    runtime = get_runtime_thread()

    watching_future = SyncWatchingFuture()

    with set_current_future(watching_future):
        if current_future is None or current_future.owner_thread_ident != runtime.ident:
            future = runtime.submit_to_loop(__fn, *args, **kwargs)
        else:
            future = current_future.send_call(__fn, *args, **kwargs)

    watching_future.wrap_future(future)
    return watching_future


def call_soon_in_worker_thread(__fn, *args, **kwargs) -> SyncWatchingFuture:
    """
    Schedule a function in a worker thread.

    Returns a watching future.
    """
    runtime = get_runtime_thread()
    future = runtime.submit_to_worker_thread(__fn, *args, **kwargs)
    return SyncWatchingFuture().wrap_future(future)


def call_soon_in_main_thread(__fn, *args, **kwargs) -> concurrent.futures.Future:
    """
    Call a function in the main thread.

    Must be used from a call scheduled by `call_soon_in_worker_thread` or
    `call_soon_in_runtime_thread` or the main thread will not be watching for work.

    Returns a future.
    """
    current_future = get_current_future()
    if current_future is None:
        raise RuntimeError("No watching future found.")

    if current_future.owner_thread_ident != threading.main_thread().ident:
        raise RuntimeError("Watching future is not owned by the main thread.")

    future = current_future.send_call(__fn, *args, **kwargs)
    return future
