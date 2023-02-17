import concurrent.futures
import threading

from prefect._internal.concurrency.runtime import get_runtime_thread
from prefect._internal.concurrency.supervisors import (
    SyncSupervisor,
    get_supervisor,
    set_supervisor,
)


def call_soon_in_runtime_thread(__fn, *args, **kwargs) -> SyncSupervisor:
    """
    Schedule a coroutine function in the runtime thread.

    Returns a supervisor.
    """
    current_future = get_supervisor()
    runtime = get_runtime_thread()

    supervisor = SyncSupervisor()

    with set_supervisor(supervisor):
        if current_future is None or current_future.owner_thread_ident != runtime.ident:
            future = runtime.submit_to_loop(__fn, *args, **kwargs)
        else:
            future = current_future.send_call(__fn, *args, **kwargs)

    supervisor.set_future(future)
    return supervisor


def call_soon_in_worker_thread(__fn, *args, **kwargs) -> SyncSupervisor:
    """
    Schedule a function in a worker thread.

    Returns a supervisor.
    """
    runtime = get_runtime_thread()
    supervisor = SyncSupervisor()
    with set_supervisor(supervisor):
        future = runtime.submit_to_worker_thread(__fn, *args, **kwargs)
    supervisor.set_future(future)
    return supervisor


def call_soon_in_main_thread(__fn, *args, **kwargs) -> concurrent.futures.Future:
    """
    Call a function in the main thread.

    Must be used from a call scheduled by `call_soon_in_worker_thread` or
    `call_soon_in_runtime_thread` or the main thread will not be watching for work.

    Returns a future.
    """
    current_future = get_supervisor()
    if current_future is None:
        raise RuntimeError("No supervisor found.")

    if current_future.owner_thread_ident != threading.main_thread().ident:
        raise RuntimeError("Watching future is not owned by the main thread.")

    future = current_future.send_call(__fn, *args, **kwargs)
    return future
