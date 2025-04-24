from __future__ import annotations

from typing import (
    Any,
    Callable,
    TypeVar,
)

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.flows import InfrastructureBoundFlow, bind_flow_to_infrastructure
from prefect_aws.workers import ECSWorker

P = ParamSpec("P")
R = TypeVar("R")


def ecs(
    work_pool: str, **job_variables: Any
) -> Callable[[Flow[P, R]], InfrastructureBoundFlow[P, R]]:
    """
    Decorator that binds execution of a flow to an ECS work pool

    Args:
        work_pool: The name of the ECS work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_aws.experimental import ecs

        @ecs(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in an ECS task
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=ECSWorker,
        )

    return decorator
