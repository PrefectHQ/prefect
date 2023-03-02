import abc
import asyncio
import concurrent.futures
from typing import Awaitable, Callable, Optional, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.runtime import get_runtime_thread
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
    def supervise_call_in_runtime_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Supervisor[T]:
        """
        Schedule a coroutine function in the runtime thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def supervise_call_in_worker_thread(
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
    def supervise_call_in_runtime_thread(
        call: Call[Awaitable[T]], timeout: Optional[float] = None
    ) -> AsyncSupervisor[Awaitable[T]]:
        current_supervisor = get_supervisor()
        runtime = get_runtime_thread()

        if (
            current_supervisor is None
            or current_supervisor.owner_thread.ident != runtime.ident
        ):
            submit_fn = runtime.submit_to_loop
        else:
            submit_fn = current_supervisor.submit_to_supervisor

        supervisor = AsyncSupervisor(call, submit_fn=submit_fn, timeout=timeout)
        supervisor.submit()
        return supervisor

    @staticmethod
    def supervise_call_in_worker_thread(
        call: Call, timeout: Optional[float] = None
    ) -> AsyncSupervisor[T]:
        runtime = get_runtime_thread()
        supervisor = AsyncSupervisor(
            call, runtime.submit_to_worker_thread, timeout=timeout
        )
        supervisor.submit()
        return supervisor

    @staticmethod
    def supervise_call_in_supervising_thread(
        call: Call, timeout: Optional[float] = None
    ) -> AsyncSupervisor:
        current_supervisor = get_supervisor()
        if current_supervisor is None:
            raise RuntimeError("No supervisor found.")

        supervisor = AsyncSupervisor(
            call, submit_fn=current_supervisor.submit_to_supervisor, timeout=timeout
        )
        supervisor.submit()
        return supervisor

    @staticmethod
    def send_call_to_supervising_thread(call: Call) -> asyncio.Future:
        current_supervisor = get_supervisor()
        if current_supervisor is None:
            raise RuntimeError("No supervisor found.")

        future = current_supervisor.send_call_to_supervisor(call)
        return asyncio.wrap_future(future)


class from_sync(_base):
    @staticmethod
    def supervise_call_in_runtime_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncSupervisor[T]:
        current_supervisor = get_supervisor()
        runtime = get_runtime_thread()

        if (
            current_supervisor is None
            or current_supervisor.owner_thread.ident != runtime.ident
        ):
            submit_fn = runtime.submit_to_loop
        else:
            submit_fn = current_supervisor.submit_to_supervisor

        supervisor = SyncSupervisor(call, submit_fn=submit_fn, timeout=timeout)
        supervisor.submit()
        return supervisor

    @staticmethod
    def supervise_call_in_worker_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncSupervisor[T]:
        runtime = get_runtime_thread()
        supervisor = SyncSupervisor(
            call, runtime.submit_to_worker_thread, timeout=timeout
        )
        supervisor.submit()
        return supervisor

    @staticmethod
    def send_call_to_supervising_thread(call: Call) -> concurrent.futures.Future:
        current_supervisor = get_supervisor()
        if current_supervisor is None:
            raise RuntimeError("No supervisor found.")

        future = current_supervisor.send_call_to_supervisor(call)
        return future

    @staticmethod
    def send_call_to_runtime_thread(call: Call) -> concurrent.futures.Future:
        current_supervisor = get_supervisor()
        runtime = get_runtime_thread()

        if (
            current_supervisor is None
            or current_supervisor.owner_thread.ident != runtime.ident
        ):
            submit_fn = runtime.submit_to_loop
        else:
            submit_fn = current_supervisor.submit_to_supervisor

        return submit_fn(call.fn, *call.args, **call.kwargs)
