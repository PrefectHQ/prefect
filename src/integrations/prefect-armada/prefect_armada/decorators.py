"""Module for defining decorators that run flows on Armada."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from typing_extensions import ParamSpec

from prefect import Flow
from prefect.flows import (
    InfrastructureBoundFlow,
    bind_flow_to_infrastructure,
)
from prefect_armada.worker import ArmadaWorker

if TYPE_CHECKING:
    from prefect.bundles import BundleLauncher

P = ParamSpec("P")
R = TypeVar("R")

__all__ = ["armada"]


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
            raise TypeError(
                f"include_files[{i}] must be a string, got {type(item).__name__}"
            )
        if not item.strip():
            raise ValueError(f"include_files[{i}] cannot be empty or whitespace-only")


def armada(
    work_pool: str,
    include_files: Sequence[str] | None = None,
    launcher: BundleLauncher | None = None,
    **job_variables: Any,
) -> Callable[[Flow[P, R]], InfrastructureBoundFlow[P, R]]:
    """
    Decorator that binds execution of a flow to an Armada work pool

    Args:
        work_pool: The name of the Armada work pool to use
        include_files: Optional sequence of file patterns to include in the bundle.
            Patterns are relative to the flow file location. Supports glob patterns
            (for example, "*.yaml", "data/**/*.csv"). Files matching these
            patterns will be bundled and available in the remote execution
            environment.
        launcher: Optional upload and execution launcher override.
        **job_variables: Additional job variables to use for infrastructure configuration

    Example:
        ```python
        from prefect import flow
        from prefect_armada.decorators import armada

        @armada(work_pool="my-pool")
        @flow
        def my_flow():
            ...

        # This will run the flow in an Armada job
        my_flow()

        # Include config files in the bundle
        @armada(work_pool="my-pool", include_files=["config.yaml", "data/"])
        @flow
        def my_flow_with_files():
            ...
        ```
    """
    # Validate include_files syntax at decoration time
    if include_files is not None:
        _validate_include_files_syntax(include_files)

    def decorator(flow: Flow[P, R]) -> InfrastructureBoundFlow[P, R]:
        """Binds the decorated flow to the Armada work pool."""
        return bind_flow_to_infrastructure(
            flow,
            work_pool=work_pool,
            job_variables=job_variables,
            worker_cls=ArmadaWorker,
            launcher=launcher,
            include_files=list(include_files) if include_files is not None else None,
        )

    return decorator
