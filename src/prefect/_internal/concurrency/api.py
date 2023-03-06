import abc
import asyncio
import concurrent.futures
from typing import Awaitable, Callable, Optional, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.supervisors import (
    AsyncSupervisor,
    Call,
    Supervisor,
    SyncSupervisor,
    get_supervisor,
)
from prefect._internal.concurrency.workers import WorkerThread, get_global_worker

P = ParamSpec("P")
T = TypeVar("T")
Future = Union[concurrent.futures.Future, asyncio.Future]


def create_call(__fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Call[T]:
    return Call.new(__fn, *args, **kwargs)


class _base(abc.ABC):
    @abc.abstractstaticmethod
    def supervise_call_in_global_worker(
        call: Call[T], timeout: Optional[float] = None
    ) -> Supervisor[T]:
        """
        Schedule a coroutine function in the runtime thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def supervise_call_in_new_worker(
        call: Call[T], timeout: Optional[float] = None
    ) -> Supervisor[T]:
        """
        Schedule a function in a worker thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def send_call_to_supervising_thread(call: Call[T]) -> Future:
        """
        Call a function in the supervising thread.

        Must be used from a call scheduled by `call_soon_in_worker_thread` or
        `call_soon_in_runtime_thread` or there will not be a supervisor.

        Returns a future.
        """
        raise NotImplementedError()


class from_async(_base):
    @staticmethod
    def supervise_call_in_global_worker(
        call: Call[Awaitable[T]], timeout: Optional[float] = None
    ) -> AsyncSupervisor[Awaitable[T]]:
        worker = get_global_worker()
        supervisor = AsyncSupervisor(call, worker=worker, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def supervise_call_in_new_worker(
        call: Call, timeout: Optional[float] = None
    ) -> AsyncSupervisor[T]:
        worker = WorkerThread(run_once=True)
        supervisor = AsyncSupervisor(call=call, worker=worker, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def send_call_to_supervising_thread(call: Call) -> asyncio.Future:
        current_supervisor = get_supervisor()
        if current_supervisor is None:
            raise RuntimeError("No supervisor found.")

        call = current_supervisor.submit(call)
        return asyncio.wrap_future(call.future)


class from_sync(_base):
    @staticmethod
    def supervise_call_in_global_worker(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncSupervisor[T]:
        worker = get_global_worker()
        supervisor = SyncSupervisor(call, worker=worker, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def supervise_call_in_new_worker(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncSupervisor[T]:
        worker = get_global_worker()
        supervisor = SyncSupervisor(call=call, worker=worker, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def send_call_to_supervising_thread(call: Call) -> concurrent.futures.Future:
        current_supervisor = get_supervisor()
        if current_supervisor is None:
            raise RuntimeError("No supervisor found.")

        call = current_supervisor.submit(call)
        return call.future
