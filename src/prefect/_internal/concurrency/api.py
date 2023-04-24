"""
Primary developer-facing API for concurrency management.
"""
import abc
import asyncio
import concurrent.futures
from typing import Awaitable, Callable, Iterable, Optional, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.calls import get_current_call
from prefect._internal.concurrency.threads import WorkerThread, get_global_loop
from prefect._internal.concurrency.waiters import AsyncWaiter, Call, SyncWaiter

P = ParamSpec("P")
T = TypeVar("T")
Future = Union[concurrent.futures.Future, asyncio.Future]


def create_call(__fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Call[T]:
    return Call.new(__fn, *args, **kwargs)


class _base(abc.ABC):
    @abc.abstractstaticmethod
    def wait_for_call_in_loop_thread(
        call: Call[T],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        """
        Schedule a function in the global worker thread.

        Returns a waiter.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def wait_for_call_in_new_thread(
        call: Call[T],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        """
        Schedule a function in a new worker thread.

        Returns a waiter.
        """
        raise NotImplementedError()

    @staticmethod
    def call_soon_in_new_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Call[T]:
        """
        Schedule a call for execution in a new worker thread.

        Returns the submitted call.
        """
        runner = WorkerThread(run_once=True)
        call.set_timeout(timeout)
        runner.submit(call)
        return call

    @staticmethod
    def call_soon_in_loop_thread(
        call: Call[Awaitable[T]], timeout: Optional[float] = None
    ) -> Call[T]:
        """
        Schedule a call for execution in the global event loop thread.

        Returns the submitted call.
        """
        runner = get_global_loop()
        call.set_timeout(timeout)
        runner.submit(call)
        return call

    @staticmethod
    def call_soon_in_waiter_thread(
        call: Call[T], timeout: Optional[float] = None
    ) -> Call[T]:
        """
        Schedule a call for execution in the thread that is waiting for the current
        call.

        Returns the submitted call.
        """
        current_call = get_current_call()
        if current_call is None:
            raise RuntimeError("No call found in context.")

        call.set_timeout(timeout)
        current_call.add_waiting_callback(call)
        return call


class from_async(_base):
    @staticmethod
    async def wait_for_call_in_loop_thread(
        call: Call[Awaitable[T]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        waiter = AsyncWaiter(call)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        _base.call_soon_in_loop_thread(call, timeout=timeout)
        await waiter.wait()
        return call.result()

    @staticmethod
    async def wait_for_call_in_new_thread(
        call: Call[T],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        waiter = AsyncWaiter(call=call)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        _base.call_soon_in_new_thread(call, timeout=timeout)
        await waiter.wait()
        return call.result()


class from_sync(_base):
    @staticmethod
    def wait_for_call_in_loop_thread(
        call: Call[Awaitable[T]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        waiter = SyncWaiter(call)
        _base.call_soon_in_loop_thread(call, timeout=timeout)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        waiter.wait()
        return call.result()

    @staticmethod
    def wait_for_call_in_new_thread(
        call: Call[T],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        waiter = SyncWaiter(call=call)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        _base.call_soon_in_new_thread(call, timeout=timeout)
        waiter.wait()
        return call.result()
