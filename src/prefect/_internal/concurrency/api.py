import abc
import asyncio
import concurrent.futures
from typing import Awaitable, Callable, Optional, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.portals import (
    WorkerThreadPortal,
    get_global_thread_portal,
)
from prefect._internal.concurrency.supervisors import (
    AsyncSupervisor,
    Call,
    Supervisor,
    SyncSupervisor,
    get_supervisor,
)

P = ParamSpec("P")
T = TypeVar("T")
Future = Union[concurrent.futures.Future, asyncio.Future]


def create_call(__fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Call[T]:
    return Call.new(__fn, *args, **kwargs)


class _base(abc.ABC):
    @abc.abstractstaticmethod
    def supervise_call_in_global_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Supervisor[T]:
        """
        Schedule a coroutine function in the runtime thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def supervise_call_in_new_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Supervisor[T]:
        """
        Schedule a function in a portal thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def send_call_to_supervising_thread(call: Call[T]) -> Future:
        """
        Call a function in the supervising thread.

        Must be used from a call scheduled by `call_soon_in_portal_thread` or
        `call_soon_in_runtime_thread` or there will not be a supervisor.

        Returns a future.
        """
        raise NotImplementedError()


class from_async(_base):
    @staticmethod
    def supervise_call_in_global_thread(
        call: Call[Awaitable[T]], timeout: Optional[float] = None
    ) -> AsyncSupervisor[Awaitable[T]]:
        portal = get_global_thread_portal()
        supervisor = AsyncSupervisor(call, portal=portal, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def supervise_call_in_new_thread(
        call: Call, timeout: Optional[float] = None
    ) -> AsyncSupervisor[T]:
        portal = WorkerThreadPortal(run_once=True)
        supervisor = AsyncSupervisor(call=call, portal=portal, timeout=timeout)
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
    def supervise_call_in_global_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncSupervisor[T]:
        portal = get_global_thread_portal()
        supervisor = SyncSupervisor(call, portal=portal, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def supervise_call_in_new_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncSupervisor[T]:
        portal = get_global_thread_portal()
        supervisor = SyncSupervisor(call=call, portal=portal, timeout=timeout)
        supervisor.start()
        return supervisor

    @staticmethod
    def send_call_to_supervising_thread(call: Call) -> concurrent.futures.Future:
        current_supervisor = get_supervisor()
        if current_supervisor is None:
            raise RuntimeError("No supervisor found.")

        call = current_supervisor.submit(call)
        return call.future
