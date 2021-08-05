import concurrent.futures
from functools import partial
from uuid import UUID
from typing import Any, Callable, Dict, Optional, TypeVar
from contextlib import contextmanager

import cloudpickle

# TODO: Once executors are split into separate files this should become an optional dependency
import distributed

from prefect.orion.schemas.states import State
from prefect.futures import resolve_futures, PrefectFuture
from prefect.client import OrionClient

T = TypeVar("T", bound="BaseExecutor")


class BaseExecutor:
    def __init__(self) -> None:
        # Set on `start`
        self.flow_run_id: str = None
        self.orion_client: OrionClient = None

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        """
        Submit a call for execution and return a `PrefectFuture` that can be used to
        get the call result. This method is responsible for resolving `PrefectFutures`
        in args and kwargs into a type supported by the underlying execution method
        """
        raise NotImplementedError()

    @contextmanager
    def start(self: T, flow_run_id: str, orion_client: "OrionClient") -> T:
        self.flow_run_id = flow_run_id
        self.orion_client = orion_client
        try:
            yield self
        finally:
            self.shutdown()
            self.flow_run_id = None
            self.orion_client = None

    def shutdown(self) -> None:
        """
        Clean up resources associated with the executor

        Should block until submitted calls are completed
        """
        pass

    def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        """
        Given a `PrefectFuture`, wait for its return state up to `timeout` seconds.
        If it is not finished after the timeout expires, `None` should be returned.
        """
        raise NotImplementedError()


class SynchronousExecutor(BaseExecutor):
    """
    A simple synchronous executor that executes calls as they are submitted
    """

    def __init__(self) -> None:
        super().__init__()
        self._results: Dict[UUID, State] = {}

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self.flow_run_id:
            raise RuntimeError("The executor must be started before submitting work.")

        # Block until all upstreams are resolved
        args, kwargs = resolve_futures((args, kwargs))

        # Run the function immediately and store the result in memory
        self._results[run_id] = run_fn(*args, **kwargs)

        return PrefectFuture(
            task_run_id=run_id,
            flow_run_id=self.flow_run_id,
            client=self.orion_client,
            executor=self,
        )

    def wait(self, prefect_future: PrefectFuture, timeout: float = None) -> State:
        return self._results[prefect_future.run_id]


class LocalPoolExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a thread or process pool
    """

    def __init__(self, processes: bool = False) -> None:
        super().__init__()
        self._pool_type = (
            concurrent.futures.ProcessPoolExecutor
            if processes
            else concurrent.futures.ThreadPoolExecutor
        )
        self._pool: concurrent.futures.Executor = None
        self._futures: Dict[UUID, concurrent.futures.Future] = {}
        self.processes = processes

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self._pool:
            raise RuntimeError("The executor must be started before submitting work.")

        if self.processes:
            # Resolve `PrefectFutures` in args/kwargs into values which will block but
            # futures not serializable; in the future we can rely on Orion to roundtrip
            # the data instead
            args, kwargs = resolve_futures((args, kwargs))
            # Use `cloudpickle` to serialize the call instead of the builtin pickle
            # since it supports more function types
            payload = _serialize_call(run_fn, *args, **kwargs)
            future = self._pool.submit(_run_serialized_call, payload)
        else:
            # Submit a function that resolves input futures then calls the task run
            # function. Delegating future resolution to the pool stops `submit` from
            # blocking parallelism.
            future = self._pool.submit(
                _resolve_futures_then_run, run_fn, *args, **kwargs
            )

        self._futures[run_id] = future

        return PrefectFuture(
            task_run_id=run_id,
            flow_run_id=self.flow_run_id,
            client=self.orion_client,
            executor=self,
        )

    def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        future = self._futures[prefect_future.run_id]
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None

    @contextmanager
    def start(self: T, flow_run_id: str, orion_client: "OrionClient") -> T:
        with super().start(flow_run_id=flow_run_id, orion_client=orion_client):
            self._pool = self._pool_type()
            yield self

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)
        self._pool = None


class DaskExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a dask cluster

    TODO: __init__ should support cluster setup kwargs as well as existing cluster
          connection args
    """

    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self._client: "distributed.Client" = None
        self._futures: Dict[UUID, "distributed.Future"] = {}
        self.debug = debug

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self._client:
            raise RuntimeError("The executor must be started before submitting work.")

        args, kwargs = resolve_futures((args, kwargs), resolve_fn=self._get_dask_future)

        self._futures[run_id] = self._client.submit(run_fn, *args, **kwargs)

        return PrefectFuture(
            task_run_id=run_id,
            flow_run_id=self.flow_run_id,
            client=self.orion_client,
            executor=self,
        )

    def _get_dask_future(self, prefect_future: PrefectFuture) -> "distributed.Future":
        return self._futures[prefect_future.run_id]

    def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        future = self._futures[prefect_future.run_id]
        try:
            return future.result(timeout=timeout)
        except distributed.TimeoutError:
            return None

    @contextmanager
    def start(self: T, flow_run_id: str, orion_client: "OrionClient") -> T:
        with super().start(flow_run_id=flow_run_id, orion_client=orion_client):
            self._client = distributed.Client()
            yield self

    def shutdown(self) -> None:
        self._client.close()


def _serialize_call(fn, *args, **kwargs):
    return cloudpickle.dumps((fn, args, kwargs))


def _run_serialized_call(payload):
    fn, args, kwargs = cloudpickle.loads(payload)
    return fn(*args, **kwargs)


def _resolve_futures_then_run(fn, *args, **kwargs):
    args, kwargs = resolve_futures((args, kwargs))
    return fn(*args, **kwargs)
