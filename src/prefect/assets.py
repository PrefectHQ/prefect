from __future__ import annotations

import re
from functools import wraps
from typing import Any, Callable, Sequence, TypeVar, cast
from uuid import UUID

from pydantic import Field, field_validator
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

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not URI_REGEX.match(value):
            raise ValueError(
                "Key must be a valid URI, e.g. storage://bucket/folder/asset.csv"
            )
        return value

    def as_resource(self) -> dict[str, str]:
        resource = {
            "prefect.resource.id": self.key,
        }
        if self.name:
            resource["prefect.resource.name"] = self.name

        if self.metadata:
            for k, v in self.metadata.items():
                resource[k] = v

        return resource

    def as_related(self) -> dict[str, str]:
        return {
            "prefect.resource.id": self.key,
            "prefect.resource.role": "asset",
        }

    def read(self) -> "ReadOnlyAsset":
        return ReadOnlyAsset(
            key=self.key, name=self.name, metadata=self.metadata.copy()
        )

    def __repr__(self) -> str:
        return f"Asset(key={self.key!r}, name={self.name!r})"


class ReadOnlyAsset(Asset):
    pass


class MaterializationTask(Task[P, R]):
    def __init__(
        self, fn: Callable[P, R], *, assets: Sequence[Asset], **task_kwargs: Any
    ) -> None:
        self.assets: list[Asset] = list(assets)

        on_completion = task_kwargs.pop("on_completion", [])
        on_fail = task_kwargs.pop("on_failure", [])
        task_kwargs["on_completion"] = [self._materialization_succeeded, *on_completion]
        task_kwargs["on_failure"] = [self._materialization_failed, *on_fail]
        super().__init__(fn=fn, **task_kwargs)

    def _materialization_succeeded(
        self, task: Any, task_run: TaskRun, state: State
    ) -> None:
        self._record_assets(task_run)
        self._emit_events(task_run, succeeded=True)

    def _materialization_failed(
        self, task: Any, task_run: TaskRun, state: State
    ) -> None:
        self._record_assets(task_run)
        self._emit_events(task_run, succeeded=False)

    def _record_assets(self, task_run: TaskRun) -> None:
        ctx = FlowRunContext.get()
        if not ctx:
            return

        ctx.task_run_assets[task_run.id] = self.assets

    def _discover_upstream_assets(self, task_run: TaskRun) -> list[Asset]:
        ctx = FlowRunContext.get()
        if not ctx:
            return []

        parents = ctx.task_run_parents
        assets = ctx.task_run_assets

        todo: list[UUID] = list(parents.get(task_run.id, set()))
        seen: set[UUID] = set()
        found: list[Asset] = []

        while todo:
            rid = todo.pop()
            if rid in seen:
                continue
            seen.add(rid)

            upstream_assets = assets.get(rid, ())
            if upstream_assets:
                for a in upstream_assets:
                    if a not in found:
                        found.append(a)
                continue

            todo.extend(parents.get(rid, ()))

        return found

    def _emit_events(self, task_run: TaskRun, *, succeeded: bool) -> None:
        upstream_assets = self._discover_upstream_assets(task_run)
        upstream_related = [a.as_related() for a in upstream_assets]

        for asset in self.assets:
            is_read = isinstance(asset, ReadOnlyAsset)
            event = (
                "prefect.asset.observation."
                if is_read
                else "prefect.asset.materialization."
            ) + ("succeeded" if succeeded else "failed")

            related = [] if is_read else upstream_related

            emit_event(
                event=event,
                resource=asset.as_resource(),
                related=related,
            )


def materialize(
    *assets: Asset, **task_kwargs: Any
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    if not assets:
        raise TypeError(
            "materialize requires at least one Asset argument, e.x. `@materialize(asset1)`"
        )

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        task = MaterializationTask(fn, assets=assets, **task_kwargs)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            return cast(R, task(*args, **kwargs))

        return cast(Callable[P, R], wrapper)

    return decorator
