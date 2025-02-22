from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.callables import get_call_parameters
from prefect_kubernetes.worker import KubernetesWorker

P = ParamSpec("P")
R = TypeVar("R")


def kubernetes(
    work_pool: str, **job_variables: Any
) -> Callable[[Flow[P, R]], Callable[P, R]]:
    """
    Decorator that binds execution of a flow to a Kubernetes work pool

    Args:
        work_pool: The name of the Kubernetes work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes import kubernetes

        @kubernetes(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in a Kubernetes job
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> Callable[P, R]:
        @wraps(flow)
        async def awrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async with KubernetesWorker(work_pool_name=work_pool) as worker:
                parameters = get_call_parameters(flow, args, kwargs)
                future = await worker.submit(
                    flow=flow, parameters=parameters, job_variables=job_variables
                )
                return await future.aresult()

        if inspect.iscoroutinefunction(flow.fn):
            return awrapper
        else:

            @wraps(flow)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                return run_coro_as_sync(awrapper(*args, **kwargs))

            return wrapper

    return decorator
