"""Module contains the Asset model and an asset-aware Prefect task decorator."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar
from typing_extensions import ParamSpec, Concatenate
from pydantic import BaseModel
from prefect import Task  # underlying decorator
from prefect.events import emit_event
from prefect.context import TaskRunContext

P = ParamSpec("P")  # parameters of the user function
Q = ParamSpec("Q")
R = TypeVar("R")  # return type of the user function
T = TypeVar("T")


class Asset(BaseModel):
    """Represents a data asset with a unique identifier."""

    key: str

    def materialize(self, related: list[dict[str, str]] | None = None) -> None:
        """Emit a message to materialize asset."""
        related = related or []
        emit_event(
            event="prefect.asset.materialization",
            resource={
                "prefect.resource.id": self.key,
                "prefect.resource.name": self.key,
                "prefect.resource.role": "asset",
            },
            related=related,
        )


def with_asset(
    decorator: Callable[Concatenate[Callable[Q, T], P], R],
    asset_hook: Callable[[Asset | list[Asset]], None],
) -> Callable[
    Concatenate[Asset | list[Asset], P],
    Callable[[Callable[Q, T]], R],
]:
    """Lift a Prefect task decorator so the first argument is an Asset (or list)."""

    def asset_decorator(
        asset: Asset | list[Asset],
        *d_args: P.args,
        **d_kwargs: P.kwargs,
    ) -> Callable[[Callable[Q, T]], R]:
        # ── actual decorator applied to the user function ──
        def lift(fn: Callable[Q, T]) -> R:
            @wraps(fn)
            def inner(*args: Q.args, **kwargs: Q.kwargs) -> T:
                asset_hook(asset)
                return fn(*args, **kwargs)

            # delegate to Prefect’s decorator / Task constructor
            return decorator(inner, *d_args, **d_kwargs)

        return lift

    return asset_decorator


def materialize_hook(assets: Asset | list[Asset]) -> None:
    """Emit a message to materialize assets."""
    related: list[dict[str, str]] = []
    if context := TaskRunContext.get():
        related.append(
            {
                "prefect.resource.id": f"prefect.task-run.{context.task_run.id}",
                "prefect.resource.name": context.task_run.name,
                "prefect.resource.role": "task-run",
            }
        )
    for asset in assets if isinstance(assets, list) else [assets]:
        asset.materialize(related=related)


materialize = with_asset(Task, materialize_hook)
