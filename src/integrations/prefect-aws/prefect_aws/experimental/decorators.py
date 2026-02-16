from __future__ import annotations

from typing import (
    Any,
    Callable,
    Sequence,
    TypeVar,
)

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.flows import InfrastructureBoundFlow, bind_flow_to_infrastructure
from prefect_aws.workers import ECSWorker

P = ParamSpec("P")
R = TypeVar("R")


def _validate_include_files_syntax(include_files: Sequence[Any]) -> None:
    """
    Validate include_files syntax at decoration time.

    Checks:
    - All items are strings
    - No empty or whitespace-only strings

    Args:
        include_files: Sequence of file patterns to validate

    Raises:
        ValueError: If any item is not a string or is empty/whitespace-only
    """
    for i, item in enumerate(include_files):
        if not isinstance(item, str):
            raise ValueError(
                f"include_files[{i}] must be a string, got {type(item).__name__}"
            )
        if not item.strip():
            raise ValueError(f"include_files[{i}] cannot be empty or whitespace-only")


def ecs(
    work_pool: str,
    include_files: Sequence[str] | None = None,
    **job_variables: Any,
) -> Callable[[Flow[P, R]], InfrastructureBoundFlow[P, R]]:
    """
    Decorator that binds execution of a flow to an ECS work pool

    Args:
        work_pool: The name of the ECS work pool to use
        include_files: Optional sequence of file patterns to include in the bundle.
            Patterns are relative to the flow file location. Supports glob patterns
            (e.g., "*.yaml", "data/**/*.csv"). Files matching these patterns will
            be bundled and available in the remote execution environment.
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

        # Include config files in the bundle
        @ecs(work_pool="my-pool", include_files=["config.yaml", "data/"])
        @flow
        def my_flow_with_files():
            ...
        ```
    """
    # Validate include_files syntax at decoration time
    if include_files is not None:
        _validate_include_files_syntax(include_files)

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=ECSWorker,
            include_files=list(include_files) if include_files is not None else None,
        )

    return decorator
