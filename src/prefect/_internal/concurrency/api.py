import abc
import asyncio
import concurrent.futures
from typing import Callable, TypeVar, Union

from typing_extensions import ParamSpec

from prefect._internal.concurrency.runtime import get_runtime_thread
from prefect._internal.concurrency.supervisors import (
    AsyncSupervisor,
    Supervisor,
    SyncSupervisor,
    get_supervisor,
)

P = ParamSpec("P")
T = TypeVar("T")
Future = Union[concurrent.futures.Future, asyncio.Future]


class _base(abc.ABC):
    @abc.abstractstaticmethod
    def call_soon_in_runtime_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> Supervisor:
        """
        Schedule a coroutine function in the runtime thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def call_soon_in_worker_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> Supervisor:
        """
        Schedule a function in a worker thread.

        Returns a supervisor.
        """
        raise NotImplementedError()

    @abc.abstractstaticmethod
    def call_soon_in_supervising_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> Future:
        """
        Call a function in the supervising thread.

        Must be used from a call scheduled by `call_soon_in_worker_thread` or
        `call_soon_in_runtime_thread` or there will not be a supervisor.

        Returns a future.
        """
        raise NotImplementedError()


class from_async(_base):
    @staticmethod
    def call_soon_in_runtime_thread(
        __call: Callable[..., T], *args, **kwargs
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
        supervisor.submit(__call, *args)
        return supervisor

    @staticmethod
    def call_soon_in_worker_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> AsyncSupervisor[T]:
        """
        Schedule a function in a worker thread.

        Returns a supervisor.
        """
        runtime = get_runtime_thread()
        supervisor = AsyncSupervisor(runtime.submit_to_worker_thread)
        supervisor.submit(__call, *args)
        return supervisor

    @staticmethod
    def call_soon_in_supervising_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> asyncio.Future:
        """
        Call a function in the supervising thread.

        Must be used from a call scheduled by `call_soon_in_worker_thread` or
        `call_soon_in_runtime_thread` or there will not be a supervisor.

        Returns a future.
        """
        current_future = get_supervisor()
        if current_future is None:
            raise RuntimeError("No supervisor found.")

        future = current_future.send_call_to_supervisor(__call, *args)
        return asyncio.wrap_future(future)


class from_sync(_base):
    @staticmethod
    def call_soon_in_runtime_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> SyncSupervisor[T]:
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

        supervisor = SyncSupervisor(submit_fn=submit_fn)
        supervisor.submit(__call, *args)
        return supervisor

    @staticmethod
    def call_soon_in_worker_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> SyncSupervisor[T]:
        """
        Schedule a function in a worker thread.

        Returns a supervisor.
        """
        runtime = get_runtime_thread()
        supervisor = SyncSupervisor(runtime.submit_to_worker_thread)
        supervisor.submit(__call, *args)
        return supervisor

    @staticmethod
    def call_soon_in_supervising_thread(
        __call: Callable[..., T], *args, **kwargs
    ) -> concurrent.futures.Future:
        """
        Call a function in the supervising thread.

        Must be used from a call scheduled by `call_soon_in_worker_thread` or
        `call_soon_in_runtime_thread` or there will not be a supervisor.

        Returns a future.
        """
        current_future = get_supervisor()
        if current_future is None:
            raise RuntimeError("No supervisor found.")

        future = current_future.send_call_to_supervisor(__call, *args)
        return future
