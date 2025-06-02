from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar, Union

from typing_extensions import ParamSpec, Unpack

from .core import Asset

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

if TYPE_CHECKING:
    from prefect.tasks import Task, TaskOptions


# TODO:
#  - task.assets = asset_objs ... should be a new class?
def materialize(
    *assets: Union[str, Asset],
    by: str | None = None,
    **task_kwargs: Unpack[TaskOptions],
) -> Callable[[Callable[P, R]], Task[P, R]]:
    """
    Decorator for materializing assets.

    Args:
        *assets: Assets to materialize
        by: An optional tool that materialized the asset e.g. "dbt" or "spark"
        **task_kwargs: Additional task configuration
    """
    if not assets:
        raise TypeError(
            "materialize requires at least one asset argument, e.g. `@materialize(asset)`"
        )

    asset_objs = [Asset(key=a) if isinstance(a, str) else a for a in assets]

    from prefect.tasks import Task

    def decorator(fn: Callable[P, R]) -> Task[P, R]:
        task = Task(fn=fn, **task_kwargs)
        task.assets = asset_objs
        task.materialized_by = by
        return task

    return decorator
