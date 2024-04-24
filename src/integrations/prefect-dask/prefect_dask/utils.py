"""
Utils to use alongside prefect-dask.
"""

from contextlib import asynccontextmanager, contextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Union

from distributed import Client, get_client

from prefect.context import FlowRunContext, TaskRunContext


def _generate_client_kwargs(
    async_client: bool,
    timeout: Optional[Union[int, float, str, timedelta]] = None,
    **client_kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Helper method to populate keyword arguments for `distributed.Client`.
    """
    flow_run_context = FlowRunContext.get()
    task_run_context = TaskRunContext.get()

    if task_run_context:
        # copies functionality of worker_client(separate_thread=False)
        # because this allows us to set asynchronous based on user's task
        input_client_kwargs = {}
        address = get_client().scheduler.address
        asynchronous = task_run_context.task.isasync
    elif flow_run_context:
        task_runner = flow_run_context.task_runner
        input_client_kwargs = task_runner.client_kwargs
        address = task_runner._client.scheduler_info()["address"]
        asynchronous = flow_run_context.flow.isasync
    else:
        # this else clause allows users to debug or test
        # without much change to code
        input_client_kwargs = {}
        address = None
        asynchronous = async_client

    input_client_kwargs["address"] = address
    input_client_kwargs["asynchronous"] = asynchronous
    if timeout is not None:
        input_client_kwargs["timeout"] = timeout
    input_client_kwargs.update(**client_kwargs)
    return input_client_kwargs


@contextmanager
def get_dask_client(
    timeout: Optional[Union[int, float, str, timedelta]] = None,
    **client_kwargs: Dict[str, Any],
) -> Generator[Client, None, None]:
    """
    Yields a temporary synchronous dask client; this is useful
    for parallelizing operations on dask collections,
    such as a `dask.DataFrame` or `dask.Bag`.

    Without invoking this, workers do not automatically get a client to connect
    to the full cluster. Therefore, it will attempt perform work within the
    worker itself serially, and potentially overwhelming the single worker.

    When in an async context, we recommend using `get_async_dask_client` instead.

    Args:
        timeout: Timeout after which to error out; has no effect in
            flow run contexts because the client has already started;
            Defaults to the `distributed.comm.timeouts.connect`
            configuration value.
        client_kwargs: Additional keyword arguments to pass to
            `distributed.Client`, and overwrites inherited keyword arguments
            from the task runner, if any.

    Yields:
        A temporary synchronous dask client.

    Examples:
        Use `get_dask_client` to distribute work across workers.
        ```python
        import dask
        from prefect import flow, task
        from prefect_dask import DaskTaskRunner, get_dask_client

        @task
        def compute_task():
            with get_dask_client(timeout="120s") as client:
                df = dask.datasets.timeseries("2000", "2001", partition_freq="4w")
                summary_df = client.compute(df.describe()).result()
            return summary_df

        @flow(task_runner=DaskTaskRunner())
        def dask_flow():
            prefect_future = compute_task.submit()
            return prefect_future.result()

        dask_flow()
        ```
    """
    client_kwargs = _generate_client_kwargs(
        async_client=False, timeout=timeout, **client_kwargs
    )
    with Client(**client_kwargs) as client:
        yield client


@asynccontextmanager
async def get_async_dask_client(
    timeout: Optional[Union[int, float, str, timedelta]] = None,
    **client_kwargs: Dict[str, Any],
) -> AsyncGenerator[Client, None]:
    """
    Yields a temporary asynchronous dask client; this is useful
    for parallelizing operations on dask collections,
    such as a `dask.DataFrame` or `dask.Bag`.

    Without invoking this, workers do not automatically get a client to connect
    to the full cluster. Therefore, it will attempt perform work within the
    worker itself serially, and potentially overwhelming the single worker.

    Args:
        timeout: Timeout after which to error out; has no effect in
            flow run contexts because the client has already started;
            Defaults to the `distributed.comm.timeouts.connect`
            configuration value.
        client_kwargs: Additional keyword arguments to pass to
            `distributed.Client`, and overwrites inherited keyword arguments
            from the task runner, if any.

    Yields:
        A temporary asynchronous dask client.

    Examples:
        Use `get_async_dask_client` to distribute work across workers.
        ```python
        import dask
        from prefect import flow, task
        from prefect_dask import DaskTaskRunner, get_async_dask_client

        @task
        async def compute_task():
            async with get_async_dask_client(timeout="120s") as client:
                df = dask.datasets.timeseries("2000", "2001", partition_freq="4w")
                summary_df = await client.compute(df.describe())
            return summary_df

        @flow(task_runner=DaskTaskRunner())
        async def dask_flow():
            prefect_future = await compute_task.submit()
            return await prefect_future.result()

        asyncio.run(dask_flow())
        ```
    """
    client_kwargs = _generate_client_kwargs(
        async_client=True, timeout=timeout, **client_kwargs
    )
    async with Client(**client_kwargs) as client:
        yield client
