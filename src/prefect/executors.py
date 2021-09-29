"""
Abstract class and implementations for executing task runs.
"""
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import UUID
from prefect.utilities.collections import visit_collection

# TODO: Once executors are split into separate files this should become an optional dependency
import distributed

import prefect
from prefect.client import OrionClient
from prefect.futures import PrefectFuture, resolve_futures_to_data
from prefect.orion.schemas.states import State

T = TypeVar("T", bound="BaseExecutor")


class BaseExecutor:
    def __init__(self) -> None:
        # Set on `start`
        self.flow_run_id: UUID = None
        self.orion_client: OrionClient = None

    async def submit(
        self,
        run_id: UUID,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        """
        Submit a call for execution and return a `PrefectFuture` that can be used to
        get the call result. This method is responsible for resolving `PrefectFutures`
        in args and kwargs into a type supported by the underlying execution method.

        Args:
            run_id: A unique id identifying the run being submitted
            run_fn: The function to be executed
            *args: Arguments to pass to `run_fn`
            **kwargs: Keyword arguments to pass to `run_fn`

        Returns:
            A future representing the result of `run_fn` execution
        """
        raise NotImplementedError()

    @contextmanager
    def start(
        self: T,
        flow_run_id: UUID,
        orion_client: "OrionClient",
    ) -> T:
        """Start the executor, preparing any resources necessary for task submission"""
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
        Clean up resources associated with the executor.

        Should block until submitted calls are completed.
        """
        # TODO: Consider adding a `wait` bool here for fast shutdown
        pass

    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        """
        Given a `PrefectFuture`, wait for its return state up to `timeout` seconds.
        If it is not finished after the timeout expires, `None` should be returned.
        """
        raise NotImplementedError()


class SequentialExecutor(BaseExecutor):
    """
    A simple executor that executes calls as they are submitted.

    If writing synchronous tasks, this executor will always run tasks sequentially.
    If writing async tasks, this executor will run tasks sequentially unless grouped
    using `anyio.create_task_group` or `asyncio.gather`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._results: Dict[UUID, State] = {}

    async def submit(
        self,
        run_id: UUID,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self.flow_run_id:
            raise RuntimeError("The executor must be started before submitting work.")

        # Block until all upstreams are resolved
        args, kwargs = await resolve_futures_to_data((args, kwargs))

        # Run the function immediately and store the result in memory
        self._results[run_id] = await run_fn(*args, **kwargs)

        return PrefectFuture(
            run_id=run_id,
            client=self.orion_client,
            executor=self,
        )

    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        return self._results[prefect_future.run_id]


class DaskExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a dask cluster.

    A local dask distributed cluster is created on use.
    """

    # TODO: __init__ should support cluster setup kwargs as well as existing cluster
    #      connection args

    def __init__(self) -> None:
        super().__init__()
        self._client: "distributed.Client" = None
        self._futures: Dict[UUID, "distributed.Future"] = {}

    async def submit(
        self,
        run_id: UUID,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self._client:
            raise RuntimeError("The executor must be started before submitting work.")

        async def visit_fn(expr):
            if isinstance(expr, PrefectFuture):
                return await self._get_data_from_future(expr)
            else:
                return expr

        args, kwargs = await visit_collection(
            (args, kwargs), visit_fn=visit_fn, return_data=True
        )

        self._futures[run_id] = self._client.submit(run_fn, *args, **kwargs)

        return PrefectFuture(
            run_id=run_id,
            client=self.orion_client,
            executor=self,
        )

    def _get_dask_future(self, prefect_future: PrefectFuture) -> "distributed.Future":
        """
        Retrieve the dask future corresponding to a prefect future

        The dask future is for the `run_fn` which should return a `State`
        """
        return self._futures[prefect_future.run_id]

    async def _get_data_from_future(
        self, prefect_future: PrefectFuture
    ) -> "distributed.Future":
        """
        Generate a dask future corresponding to a prefect future that will retrieve the
        data from the resulting state
        """
        dask_state_future = self._get_dask_future(prefect_future)
        data_future = self._client.submit(prefect.get_result, dask_state_future)
        return data_future

    async def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        future = self._get_dask_future(prefect_future)
        try:
            return future.result(timeout=timeout)
        except distributed.TimeoutError:
            return None

    @contextmanager
    def start(self: T, flow_run_id: UUID, orion_client: "OrionClient") -> T:
        with super().start(flow_run_id=flow_run_id, orion_client=orion_client):
            self._client = distributed.Client()
            yield self

    def shutdown(self) -> None:
        # Attempt to wait for all futures to complete
        for future in self._futures.values():
            try:
                future.result()
            except Exception:
                pass
        self._client.close()
