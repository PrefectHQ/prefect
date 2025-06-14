from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar, Union, overload

from typing_extensions import ParamSpec, Unpack

from .core import Asset

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

if TYPE_CHECKING:
    from prefect.tasks import MaterializingTask, TaskOptions


# Overload for using @materialize without arguments
@overload
def materialize(__fn: Callable[P, R]) -> MaterializingTask[P, R]: ...


# Overload for using @materialize with assets and/or kwargs
@overload
def materialize(
    *assets: Union[str, Asset],
    by: str | None = None,
    **task_kwargs: Unpack[TaskOptions],
) -> Callable[[Callable[P, R]], MaterializingTask[P, R]]: ...


def materialize(
    __fn_or_asset: Union[Callable[P, R], str, Asset, None] = None,
    *assets: Union[str, Asset],
    by: str | None = None,
    **task_kwargs: Unpack[TaskOptions],
) -> Union[
    MaterializingTask[P, R], Callable[[Callable[P, R]], MaterializingTask[P, R]]
]:
    """
    Decorator for materializing assets.

    Can be used with or without arguments:

    ```python
    # Without arguments
    @materialize
    def my_task():
        pass

    # With assets
    @materialize("asset1", "asset2")
    def my_task():
        pass

    # With kwargs only
    @materialize(by="dbt", name="my_task")
    def my_task():
        pass
    ```

    Args:
        *assets: Assets to materialize (can be strings or Asset objects)
        by: An optional tool that is ultimately responsible for materializing the asset e.g. "dbt" or "spark"
        **task_kwargs: Additional task configuration passed to MaterializingTask

    Returns:
        When used without arguments, returns a MaterializingTask directly.
        When used with arguments, returns a decorator function.
    """
    from prefect.tasks import MaterializingTask

    if __fn_or_asset is not None:
        if callable(__fn_or_asset):
            return MaterializingTask(
                fn=__fn_or_asset, assets=[], materialized_by=by, **task_kwargs
            )
        elif isinstance(__fn_or_asset, (str, Asset)):
            assets = (__fn_or_asset,) + assets

    def decorator(fn: Callable[P, R]) -> MaterializingTask[P, R]:
        if not callable(fn):
            raise TypeError(f"'{fn}' must be callable")

        return MaterializingTask(
            fn=fn, assets=list(assets), materialized_by=by, **task_kwargs
        )

    return decorator
