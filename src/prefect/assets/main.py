"""Module contains the Asset model and an asset-aware Prefect task decorator."""

from __future__ import annotations
from functools import wraps
from typing import Any, Callable, TypeVar, TYPE_CHECKING
from typing_extensions import ParamSpec, Concatenate
from pydantic import BaseModel
from prefect import Task  # underlying decorator
from prefect.events import emit_event
from prefect.utilities.events import get_related_resource_from_context

if TYPE_CHECKING:
    from prefect.transactions import Transaction
    from prefect.tasks import TaskRun, State, StateHookCallable

P = ParamSpec("P")  # parameters of the user function
Q = ParamSpec("Q")
R = TypeVar("R")  # return type of the user function
T = TypeVar("T")


class Asset(BaseModel):
    """Represents a data asset with a unique identifier."""

    key: str

    def _event(self, event: str, related: list[dict[str, str]] | None = None) -> None:
        """Emit an event for the asset."""
        related = related or []
        emit_event(
            event=f"prefect.asset.{event}",
            resource={
                "prefect.resource.id": self.key,
                "prefect.resource.name": self.key,
                "prefect.resource.role": "asset",
            },
            related=related,
        )

    def emit_materialization_event(
        self, related: list[dict[str, str]] | None = None
    ) -> None:
        """Emit an event to materialize asset."""
        self._event("materialization", related)

    def emit_materialization_failure_event(
        self, related: list[dict[str, str]] | None = None
    ) -> None:
        """Emit an event to materialize asset."""
        self._event("materialization.failed", related)


def with_asset(
    decorator: Callable[Concatenate[Callable[Q, T], P], R],
    on_commit: Callable[[Asset | list[Asset]], Callable[[Transaction], None]],
    on_failure: Callable[[Asset | list[Asset]], StateHookCallable],
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
                return fn(*args, **kwargs)

            return decorator(
                inner,
                *d_args,
                **{
                    **d_kwargs,
                    "on_commit": [*d_kwargs.get("on_commit", []), on_commit(asset)],  # type: ignore
                    "on_failure": [*d_kwargs.get("on_failure", []), on_failure(asset)],  # type: ignore
                },
            )

        return lift

    return asset_decorator


def materialize_hook(assets: Asset | list[Asset]) -> Callable[[Transaction], None]:
    """Emit a message to materialize assets."""

    def record_materialization(transaction: Transaction) -> None:
        for asset in assets if isinstance(assets, list) else [assets]:
            asset.emit_materialization_event(
                related=get_related_resource_from_context()
            )

    return record_materialization


def materialize_failure_hook(
    assets: Asset | list[Asset],
) -> StateHookCallable:
    def record_materialization_failure(
        task: Task[..., Any], task_run: "TaskRun", state: "State"
    ) -> None:
        for asset in assets if isinstance(assets, list) else [assets]:
            asset.emit_materialization_failure_event(
                related=get_related_resource_from_context()
            )

    return record_materialization_failure


materialize = with_asset(Task, materialize_hook, materialize_failure_hook)
