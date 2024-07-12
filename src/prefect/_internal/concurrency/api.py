"""
Primary developer-facing API for concurrency management.
"""

import abc
import asyncio
import concurrent.futures
import contextlib
from typing import (
    Awaitable,
    Callable,
    ContextManager,
    Iterable,
    Optional,
    TypeVar,
    Union,
)

from typing_extensions import ParamSpec

from prefect._internal.concurrency.threads import (
    WorkerThread,
    get_global_loop,
    in_global_loop,
)
from prefect._internal.concurrency.waiters import (
    AsyncWaiter,
    Call,
    SyncWaiter,
)

P = ParamSpec("P")
T = TypeVar("T")
Future = Union[concurrent.futures.Future, asyncio.Future]


def create_call(__fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Call[T]:
    return Call.new(__fn, *args, **kwargs)


def _cast_to_call(call_like: Union[Callable[[], T], Call[T]]) -> Call[T]:
    if isinstance(call_like, Call):
        return call_like
    else:
        return create_call(call_like)


class _base(abc.ABC):
    @abc.abstractstaticmethod
    def wait_for_call_in_loop_thread(
        __call: Union[Callable[[], T], Call[T]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> T:
        """
        Schedule a function in the global worker thread and wait for completion.

        Returns the result of the call.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def wait_for_call_in_new_thread(
        __call: Union[Callable[[], T], Call[T]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> T:
        """
        Schedule a function in a new worker thread.

        Returns the result of the call.
        """
        raise NotImplementedError()

    @staticmethod
    def call_soon_in_new_thread(
        __call: Union[Callable[[], T], Call[T]], timeout: Optional[float] = None
    ) -> Call[T]:
        """
        Schedule a call for execution in a new worker thread.

        Returns the submitted call.
        """
        call = _cast_to_call(__call)
        runner = WorkerThread(run_once=True)
        call.set_timeout(timeout)
        runner.submit(call)
        return call

    @staticmethod
    def call_soon_in_loop_thread(
        __call: Union[Callable[[], Awaitable[T]], Call[Awaitable[T]]],
        timeout: Optional[float] = None,
    ) -> Call[T]:
        """
        Schedule a call for execution in the global event loop thread.

        Returns the submitted call.
        """
        call = _cast_to_call(__call)
        runner = get_global_loop()
        call.set_timeout(timeout)
        runner.submit(call)
        return call

    @staticmethod
    def call_in_new_thread(
        __call: Union[Callable[[], T], Call[T]], timeout: Optional[float] = None
    ) -> T:
        """
        Run a call in a new worker thread.

        Returns the result of the call.
        """
        raise NotImplementedError()

    @staticmethod
    def call_in_loop_thread(
        __call: Union[Callable[[], Awaitable[T]], Call[Awaitable[T]]],
        timeout: Optional[float] = None,
    ) -> T:
        """
        Run a call in the global event loop thread.

        Returns the result of the call.
        """
        raise NotImplementedError()


class from_async(_base):
    @staticmethod
    async def wait_for_call_in_loop_thread(
        __call: Union[Callable[[], Awaitable[T]], Call[Awaitable[T]]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
        contexts: Optional[Iterable[ContextManager]] = None,
    ) -> Awaitable[T]:
        call = _cast_to_call(__call)
        waiter = AsyncWaiter(call)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        _base.call_soon_in_loop_thread(call, timeout=timeout)
        with contextlib.ExitStack() as stack:
            for context in contexts or []:
                stack.enter_context(context)
            await waiter.wait()
            return call.result()

    @staticmethod
    async def wait_for_call_in_new_thread(
        __call: Union[Callable[[], T], Call[T]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> T:
        call = _cast_to_call(__call)
        waiter = AsyncWaiter(call=call)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        _base.call_soon_in_new_thread(call, timeout=timeout)
        await waiter.wait()
        return call.result()

    @staticmethod
    def call_in_new_thread(
        __call: Union[Callable[[], T], Call[T]], timeout: Optional[float] = None
    ) -> Awaitable[T]:
        call = _base.call_soon_in_new_thread(__call, timeout=timeout)
        return call.aresult()

    @staticmethod
    def call_in_loop_thread(
        __call: Union[Callable[[], Awaitable[T]], Call[Awaitable[T]]],
        timeout: Optional[float] = None,
    ) -> Awaitable[T]:
        call = _base.call_soon_in_loop_thread(__call, timeout=timeout)
        return call.aresult()


class from_sync(_base):
    @staticmethod
    def wait_for_call_in_loop_thread(
        __call: Union[
            Callable[[], Awaitable[T]],
            Union[Callable[[], Awaitable[T]], Call[Awaitable[T]]],
        ],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
        contexts: Optional[Iterable[ContextManager]] = None,
    ) -> Awaitable[T]:
        call = _cast_to_call(__call)
        waiter = SyncWaiter(call)
        _base.call_soon_in_loop_thread(call, timeout=timeout)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        with contextlib.ExitStack() as stack:
            for context in contexts or []:
                stack.enter_context(context)
            waiter.wait()
            return call.result()

    @staticmethod
    def wait_for_call_in_new_thread(
        __call: Union[Callable[[], T], Call[T]],
        timeout: Optional[float] = None,
        done_callbacks: Optional[Iterable[Call]] = None,
    ) -> Call[T]:
        call = _cast_to_call(__call)
        waiter = SyncWaiter(call=call)
        for callback in done_callbacks or []:
            waiter.add_done_callback(callback)
        _base.call_soon_in_new_thread(call, timeout=timeout)
        waiter.wait()
        return call.result()

    @staticmethod
    def call_in_new_thread(
        __call: Union[Callable[[], T], Call[T]], timeout: Optional[float] = None
    ) -> T:
        call = _base.call_soon_in_new_thread(__call, timeout=timeout)
        return call.result()

    @staticmethod
    def call_in_loop_thread(
        __call: Union[Callable[[], Awaitable[T]], Call[Awaitable[T]]],
        timeout: Optional[float] = None,
    ) -> T:
        if in_global_loop():
            # Avoid deadlock where the call is submitted to the loop then the loop is
            # blocked waiting for the call
            call = _cast_to_call(__call)
            return call()

        call = _base.call_soon_in_loop_thread(__call, timeout=timeout)
        return call.result()
