from typing import Any, Callable, TypeVar

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.flows import InfrastructureBoundFlow, bind_flow_to_infrastructure
from prefect_docker.worker import DockerWorker

P = ParamSpec("P")
R = TypeVar("R")


def docker(work_pool: str, **job_variables: Any) -> Callable[[Flow[P, R]], Flow[P, R]]:
    """
    Decorator that binds execution of a flow to a Docker work pool

    Args:
        work_pool: The name of the Docker work pool to use
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_docker import docker

        @docker(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in a Docker container
        my_flow()
        ```
    """

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=DockerWorker,
        )

    return decorator
