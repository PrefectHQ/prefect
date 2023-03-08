"""
Primary developer-facing API for concurrency management.
"""
import abc
import asyncio
import concurrent.futures
from typing import Awaitable, Callable, Optional, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.calls import get_current_call
from prefect._internal.concurrency.threads import WorkerThread, get_global_thread_portal
from prefect._internal.concurrency.waiters import AsyncWaiter, Call, SyncWaiter, Waiter

P = ParamSpec("P")
T = TypeVar("T")
Future = Union[concurrent.futures.Future, asyncio.Future]


def create_call(__fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Call[T]:
    return Call.new(__fn, *args, **kwargs)


class _base(abc.ABC):
    @abc.abstractstaticmethod
    def call_soon_in_global_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Waiter[T]:
        """
        Schedule a function in the global worker thread.

        Returns a waiter.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def call_soon_in_new_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Waiter[T]:
        """
        Schedule a function in a new worker thread.

        Returns a waiter.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def send_callback(call: Call[T], timeout: Optional[float] = None) -> Future:
        """
        Add a callback for the current call.

        Typically schedules the callback for execution in a monitoring thread.

        Returns a future.
        """
        raise NotImplementedError()


class from_async(_base):
    @staticmethod
    def call_soon_in_global_thread(
        call: Call[Awaitable[T]], timeout: Optional[float] = None
    ) -> AsyncWaiter[Awaitable[T]]:
        portal = get_global_thread_portal()
        call.set_timeout(timeout)
        waiter = AsyncWaiter(call)
        portal.submit(call)
        return waiter

    @staticmethod
    def call_soon_in_new_thread(
        call: Call, timeout: Optional[float] = None
    ) -> AsyncWaiter[T]:
        portal = WorkerThread(run_once=True)
        call.set_timeout(timeout)
        waiter = AsyncWaiter(call=call)
        portal.submit(call)
        return waiter

    @staticmethod
    def send_callback(call: Call, timeout: Optional[float] = None) -> asyncio.Future:
        current_call = get_current_call()
        if current_call is None:
            raise RuntimeError("No call found in context.")

        call.set_timeout(timeout)
        current_call.add_callback(call)
        return asyncio.wrap_future(call.future)


class from_sync(_base):
    @staticmethod
    def call_soon_in_global_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncWaiter[T]:
        portal = get_global_thread_portal()
        call.set_timeout(timeout)
        waiter = SyncWaiter(call)
        portal.submit(call)
        return waiter

    @staticmethod
    def call_soon_in_new_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> SyncWaiter[T]:
        portal = get_global_thread_portal()
        call.set_timeout(timeout)
        waiter = SyncWaiter(call=call)
        portal.submit(call)
        return waiter

    @staticmethod
    def send_callback(
        call: Call, timeout: Optional[float] = None
    ) -> concurrent.futures.Future:
        current_call = get_current_call()
        if current_call is None:
            raise RuntimeError("No call found in context.")

        call.set_timeout(timeout)
        current_call.add_callback(call)
        return call.future
