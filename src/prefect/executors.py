import concurrent.futures
from functools import partial
from typing import Any, Callable, Dict, Optional

import cloudpickle

# TODO: Once executors are split into separate files this should become an optional dependency
import distributed

from prefect.orion.schemas.states import State
from prefect.futures import resolve_futures, PrefectFuture


class BaseExecutor:
    def __init__(self) -> None:
        pass

    def submit(
        self,
        run_id: str,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        """
        Submit a call for execution and return a callable that can be used to wait for
        the call's result; this method is responsible for resolving `PrefectFutures`
        in args/kwargs into a type supported by the underlying execution method
        """
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    def shutdown(self) -> None:
        """
        Clean up resources associated with the executor

        Will block until submitted calls are completed
        """
        pass


class SynchronousExecutor(BaseExecutor):
    """
    A simple synchronous executor that executes calls as they are submitted
    """

    def __init__(self) -> None:
        super().__init__()

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        # Block until all upstreams are resolved
        args, kwargs = resolve_futures((args, kwargs))
        # Run the function immediately
        result = run_fn(*args, **kwargs)
        # Return a fake 'wait'
        return partial(self._wait, result)

    def _wait(self, result: State, timeout: float = None):
        # Just return the given result
        return result


class LocalPoolExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a thread or process pool
    """

    def __init__(self, debug: bool = False, processes: bool = False) -> None:
        super().__init__()
        self._pool_type = (
            concurrent.futures.ProcessPoolExecutor
            if processes
            else concurrent.futures.ThreadPoolExecutor
        )
        self._pool: concurrent.futures.Executor = None
        self.debug = debug
        self.processes = processes

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        if not self._pool:
            raise RuntimeError(
                "The executor context must be entered before submitting work."
            )

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

        if self.debug:
            future.result()

        return partial(self._wait, future)

    def _wait(
        self,
        future: concurrent.futures.Future,
        timeout: float = None,
    ) -> Optional[State]:
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None

    def __enter__(self):
        # Create the pool when entered
        self._pool = self._pool_type()
        return self

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
        self._run_to_future: Dict[str, "distributed.Future"] = {}
        self.debug = debug

    def submit(
        self,
        run_id: str,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        if not self._client:
            raise RuntimeError(
                "The executor context must be entered before submitting work."
            )

        args, kwargs = resolve_futures((args, kwargs), resolve_fn=self._get_dask_future)

        future = self._client.submit(run_fn, *args, **kwargs)

        self._run_to_future[run_id] = future

        if self.debug:
            future.result()

        return partial(self._wait, future)

    def _get_dask_future(self, prefect_future: PrefectFuture) -> "distributed.Future":
        return self._run_to_future[prefect_future.run_id]

    def _wait(
        self,
        future: "distributed.Future",
        timeout: float = None,
    ) -> Optional[State]:
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None

    def __enter__(self):
        # Create the pool when entered
        self._client = distributed.Client()
        self._client.__enter__()
        return self

    def shutdown(self) -> None:
        self._client.__exit__(None, None, None)


def _serialize_call(fn, *args, **kwargs):
    return cloudpickle.dumps((fn, args, kwargs))


def _run_serialized_call(payload):
    fn, args, kwargs = cloudpickle.loads(payload)
    return fn(*args, **kwargs)


def _resolve_futures_then_run(fn, *args, **kwargs):
    args, kwargs = resolve_futures((args, kwargs))
    return fn(*args, **kwargs)
