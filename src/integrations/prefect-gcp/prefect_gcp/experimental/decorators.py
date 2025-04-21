from __future__ import annotations

from typing import (
    Any,
    Callable,
    TypeVar,
)

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.flows import InfrastructureBoundFlow, bind_flow_to_infrastructure
from prefect_gcp.workers.cloud_run_v2 import CloudRunWorkerV2
from prefect_gcp.workers.vertex import VertexAIWorker

P = ParamSpec("P")
R = TypeVar("R")


def cloud_run(
    work_pool: str, **job_variables: Any
) -> Callable[[Flow[P, R]], InfrastructureBoundFlow[P, R]]:
    """
    Decorator that binds execution of a flow to a Cloud Run V2 work pool

    Args:
        work_pool: The name of the Cloud Run V2 work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_gcp.experimental import cloud_run

        @cloud_run(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in a Cloud Run job
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=CloudRunWorkerV2,
        )

    return decorator


def vertex_ai(
    work_pool: str, **job_variables: Any
) -> Callable[[Flow[P, R]], InfrastructureBoundFlow[P, R]]:
    """
    Decorator that binds execution of a flow to a Vertex AI work pool

    Args:
        work_pool: The name of the Vertex AI work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_gcp.experimental import vertex_ai

        @vertex_ai(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in a Vertex AI custom training job
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=VertexAIWorker,
        )

    return decorator
