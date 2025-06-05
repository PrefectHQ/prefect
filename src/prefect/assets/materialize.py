from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar, Union

from typing_extensions import ParamSpec, Unpack

from .core import Asset

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

if TYPE_CHECKING:
    from prefect.tasks import MaterializingTask, TaskOptions


def materialize(
    *assets: Union[str, Asset],
    by: str | None = None,
    **task_kwargs: Unpack[TaskOptions],
) -> Callable[[Callable[P, R]], MaterializingTask[P, R]]:
    """
    Decorator for materializing assets.

    Args:
        *assets: Assets to materialize
        by: An optional tool that is ultimately responsible for materializing the asset e.g. "dbt" or "spark"
        **task_kwargs: Additional task configuration
    """
    if not assets:
        raise TypeError(
            "materialize requires at least one asset argument, e.g. `@materialize(asset)`"
        )

    from prefect.tasks import MaterializingTask

    def decorator(fn: Callable[P, R]) -> MaterializingTask[P, R]:
        return MaterializingTask(
            fn=fn, assets=assets, materialized_by=by, **task_kwargs
        )

    return decorator
