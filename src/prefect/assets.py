from __future__ import annotations

import re
from functools import partial
from typing import Any, Callable, Sequence, TypeVar
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator
from typing_extensions import ParamSpec

from prefect import Task
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import TaskRun
from prefect.context import FlowRunContext
from prefect.events import emit_event
from prefect.states import State

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


URI_REGEX = re.compile(r"^[a-z0-9]+://")


class Asset(PrefectBaseModel):
    key: str
    name: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not URI_REGEX.match(value):
            raise ValueError(
                "Key must be a valid URI, e.g. storage://bucket/folder/asset.csv"
            )
        return value

    def ref(self) -> "AssetRef":
        return AssetRef(key=self.key, name=self.name, metadata=self.metadata.copy())

    def __repr__(self) -> str:
        return f"Asset(key={self.key!r}, name={self.name!r})"

    def __hash__(self) -> int:
        return hash(self.key)


class AssetRef(Asset):
    model_config = ConfigDict(frozen=True)


class MaterializationTask(Task[P, R]):
    def __init__(
        self, fn: Callable[P, R], *, assets: Sequence[Asset], **task_kwargs: Any
    ) -> None:
        self.assets: list[Asset] = list(assets)

        on_completion = task_kwargs.pop("on_completion", [])
        on_failure = task_kwargs.pop("on_failure", [])

        # Avoid logging when running this rollback hook since it is not user-defined
        succeeded_hook = partial(self._materialization_succeeded)
        succeeded_hook.log_on_run = False
        failed_hook = partial(self._materialization_failed)
        failed_hook.log_on_run = False

        task_kwargs["on_completion"] = [succeeded_hook, *on_completion]
        task_kwargs["on_failure"] = [failed_hook, *on_failure]
        super().__init__(fn=fn, **task_kwargs)

    def _materialization_succeeded(
        self, task: Any, task_run: TaskRun, state: State
    ) -> None:
        self._record_assets(task_run)

        if state.name == "Cached":
            return

        self._emit_events(task_run, succeeded=True)

    def _materialization_failed(
        self, task: Any, task_run: TaskRun, state: State
    ) -> None:
        self._record_assets(task_run)

        if state.name == "Cached":
            return

        self._emit_events(task_run, succeeded=False)

    def _record_assets(self, task_run: TaskRun) -> None:
        ctx = FlowRunContext.get()
        if not ctx:
            return

        ctx.task_run_assets[task_run.id] = self.assets

    @staticmethod
    def _discover_upstream_assets(task_run: TaskRun) -> set[Asset]:
        ctx = FlowRunContext.get()
        if not ctx:
            return set()

        parents = ctx.task_run_parents
        assets = ctx.task_run_assets

        todo: list[UUID] = list(parents.get(task_run.id, set()))
        seen: set[UUID] = set()
        found: set[Asset] = set()

        while todo:
            run_id = todo.pop()
            if run_id in seen:
                continue
            seen.add(run_id)

            upstream_assets = assets.get(run_id, ())
            if upstream_assets:
                for a in upstream_assets:
                    if a not in found:
                        found.add(a)
                continue

            todo.extend(parents.get(run_id, set()))

        return found

    @staticmethod
    def _asset_as_resource(asset: Asset) -> dict[str, str]:
        resource = {
            "prefect.resource.id": asset.key,
        }
        if asset.name:
            resource["prefect.resource.name"] = asset.name

        if asset.metadata:
            for k, v in asset.metadata.items():
                resource[k] = v

        return resource

    @staticmethod
    def _asset_as_related(asset: Asset) -> dict[str, str]:
        return {
            "prefect.resource.id": asset.key,
            "prefect.resource.role": "asset",
        }

    def _emit_events(self, task_run: TaskRun, *, succeeded: bool) -> None:
        upstream_assets = self._discover_upstream_assets(task_run)
        upstream_related = [self._asset_as_related(a) for a in upstream_assets]

        for asset in self.assets:
            is_read = isinstance(asset, AssetRef)
            event = (
                "prefect.asset.observation."
                if is_read
                else "prefect.asset.materialization."
            ) + ("succeeded" if succeeded else "failed")

            related = [] if is_read else upstream_related

            emit_event(
                event=event,
                resource=self._asset_as_resource(asset),
                related=related,
            )


def materialize(
    *assets: Asset,
    **task_kwargs: Any,
) -> Callable[[Callable[P, R]], MaterializationTask[P, R]]:
    if not assets:
        raise TypeError(
            "materialize requires at least one Asset argument, e.g. `@materialize(asset1)`"
        )

    def decorator(fn: Callable[P, R]) -> MaterializationTask[P, R]:
        return MaterializationTask(fn, assets=assets, **task_kwargs)

    return decorator
