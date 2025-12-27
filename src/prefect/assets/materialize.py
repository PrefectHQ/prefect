from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar, Union

from typing_extensions import ParamSpec, Unpack

from .core import Asset

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

if TYPE_CHECKING:
    from prefect.tasks import MaterializingTask, TaskOptions


class _MaterializeCallable:
    """
    A callable that supports both decorator and direct materialization usage.
    """

    def __init__(
        self,
        assets: tuple[Union[str, Asset], ...],
        by: str | None = None,
        **task_kwargs: Unpack[TaskOptions],
    ):
        """
        Initialize the materialize callable.

        Args:
            assets: Assets to materialize
            by: Optional tool that materialized the asset
            **task_kwargs: Additional task configuration (only used when used as decorator)
        """
        self.assets = assets
        self.by = by
        self.task_kwargs = task_kwargs
        self._materialized = False

    def __call__(
        self, fn: Callable[P, R] | None = None
    ) -> MaterializingTask[P, R] | None:
        """
        If called with a function, acts as a decorator.
        If called without arguments, attempts direct materialization.
        """
        if fn is not None:
            # Decorator usage: @materialize(asset) def fn(): ...
            from prefect.tasks import MaterializingTask

            return MaterializingTask(
                fn=fn, assets=self.assets, materialized_by=self.by, **self.task_kwargs
            )
        else:
            # Direct materialization: materialize(asset)
            if not self._materialized:
                self._materialize_directly()
                self._materialized = True
            return None

    def _materialize_directly(self) -> None:
        """
        Materialize assets directly in the current context.
        """
        from prefect.context import AssetContext, EngineContext, TaskRunContext

        # Normalize assets to Asset objects
        asset_objects = [Asset(key=a) if isinstance(a, str) else a for a in self.assets]

        # Try to get existing AssetContext (e.g., from within a task)
        # The task engine should have created this for tasks, but we handle the case where it doesn't exist
        asset_ctx = AssetContext.get()

        # If no AssetContext exists, try to create one
        if asset_ctx is None:
            task_run_ctx = TaskRunContext.get()
            flow_run_ctx = EngineContext.get()

            if task_run_ctx is not None:
                # We're in a task context - create AssetContext from task
                # Note: The task engine should have created this, but we create it as a fallback
                asset_ctx = AssetContext.from_task_and_inputs(
                    task=task_run_ctx.task,
                    task_run_id=task_run_ctx.task_run.id,
                    task_inputs=None,
                )
                asset_ctx.set()
            elif flow_run_ctx is not None and flow_run_ctx.flow_run is not None:
                # We're in a flow context but not in a task
                # Create a minimal AssetContext without task association
                # For flow-level materialization, we'll emit events directly
                asset_ctx = AssetContext(
                    downstream_assets=set(),
                    upstream_assets=set(),
                    direct_asset_dependencies=set(),
                    materialized_by=self.by,
                    task_run_id=None,
                    materialization_metadata={},
                )
                asset_ctx.set()
            else:
                raise RuntimeError(
                    "Cannot materialize assets outside of a flow or task context. "
                    "Use @materialize as a decorator or call materialize() from within a flow or task."
                )

        # Add assets to downstream_assets
        asset_ctx.downstream_assets.update(asset_objects)

        # Update materialized_by if provided
        if self.by is not None:
            asset_ctx.materialized_by = self.by

        # Update tracked assets if we have a task_run_id
        if asset_ctx.task_run_id is not None:
            asset_ctx.update_tracked_assets()
        else:
            # For flow-level materialization (no task_run_id), emit events directly
            # Create a completed state to emit success events
            from prefect.states import Completed

            completed_state = Completed()
            asset_ctx.emit_events(completed_state)


def materialize(
    *assets: Union[str, Asset],
    by: str | None = None,
    **task_kwargs: Unpack[TaskOptions],
) -> Union[
    _MaterializeCallable,
    Callable[[Callable[P, R]], MaterializingTask[P, R]],
    None,
]:
    """
    Materialize assets. Can be used as a decorator or called directly.

    When used as a decorator:
        @materialize("s3://bucket/data.csv")
        def my_task():
            ...

    When called directly (from within a flow or task):
        @flow
        def my_flow():
            materialize("s3://bucket/data.csv")

        @task
        def my_task():
            materialize("s3://bucket/data.csv")

    Args:
        *assets: Assets to materialize
        by: An optional tool that is ultimately responsible for materializing the asset e.g. "dbt" or "spark"
        **task_kwargs: Additional task configuration (only used when used as decorator)

    Returns:
        When used as decorator: A MaterializingTask (via the returned callable)
        When called directly in execution context: None (assets are materialized immediately)
        When called outside execution context: A callable for decorator use
    """
    if not assets:
        raise TypeError(
            "materialize requires at least one asset argument, e.g. `@materialize(asset)`"
        )

    materialize_obj = _MaterializeCallable(assets, by, **task_kwargs)

    # Check if we're in an execution context where we can materialize directly
    # We only materialize immediately if we're in a task or flow execution context
    # (not at definition time, which would break decorator usage)
    try:
        from prefect.context import EngineContext, TaskRunContext

        task_ctx = TaskRunContext.get()
        flow_ctx = EngineContext.get()

        # Only materialize immediately if we're in an active execution context
        # This distinguishes between definition time (decorator) and execution time (direct call)
        if task_ctx is not None or (
            flow_ctx is not None and flow_ctx.flow_run is not None
        ):
            # We're in an execution context - materialize immediately
            materialize_obj._materialize_directly()
            materialize_obj._materialized = True
            return None
    except Exception:
        # If context access fails, assume decorator usage
        pass

    # Return the callable for decorator use
    return materialize_obj
