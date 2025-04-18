from __future__ import annotations

from typing import (
    Any,
    Callable,
    TypeVar,
)

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.flows import InfrastructureBoundFlow, bind_flow_to_infrastructure
from prefect_azure.workers.container_instance import AzureContainerWorker

P = ParamSpec("P")
R = TypeVar("R")


def azure_container_instance(
    work_pool: str, **job_variables: Any
) -> Callable[[Flow[P, R]], InfrastructureBoundFlow[P, R]]:
    """
    Decorator that binds execution of a flow to an Azure Container Instance work pool

    Args:
        work_pool: The name of the Azure Container Instance work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_azure.experimental import azure_container_instance

        @azure_container_instance(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in an Azure Container Instance
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=AzureContainerWorker,
        )

    return decorator
