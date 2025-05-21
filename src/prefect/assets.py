from __future__ import annotations

import re
from functools import wraps
from typing import Callable, Dict, Generic, Sequence, TypeVar
from uuid import UUID

from pydantic import Field, field_validator

from prefect import Task
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import TaskRun
from prefect.context import FlowRunContext
from prefect.events import emit_event
from prefect.states import State

T = TypeVar("T")
P = TypeVar("P")
R = TypeVar("R")


URI_REGEX = re.compile(r"^[a-z0-9]+://")


class Asset(PrefectBaseModel):
    key: str
    name: str | None = None
    metadata: Dict[str, str] = Field(default_factory=dict)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not URI_REGEX.match(value):
            raise ValueError("key must match URI pattern '^[a-z0-9]+://'")
        return value

    def as_resource(self) -> Dict[str, str]:
        resource = {
            "prefect.resource.id": self.key,
        }
        if self.name:
            resource["prefect.resource.name"] = self.name

        resource.update(self.metadata)
        return resource

    def as_related(self) -> Dict[str, str]:
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


class MaterializationTask(Task, Generic[P, R]):
    def __init__(self, fn: Callable[..., R], *, assets: Sequence[Asset], **task_kwargs):
        self.assets: list[Asset] = list(assets)

        on_completion = task_kwargs.pop("on_completion", [])
        on_fail = task_kwargs.pop("on_failure", [])
        task_kwargs["on_completion"] = [self._materialization_succeeded, *on_completion]
        task_kwargs["on_failure"] = [self._materialization_failed, *on_fail]
        super().__init__(fn=fn, **task_kwargs)

    def _materialization_succeeded(self, task, task_run: TaskRun, state: State):
        self._record_assets(task_run)
        self._emit_events(task_run, succeeded=True)

    def _materialization_failed(self, task, task_run: TaskRun, state: State):
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

            for a in assets.get(rid, ()):
                if a not in found:
                    found.append(a)

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


def materialize(*assets: Asset, **task_kwargs):
    if not assets:
        raise TypeError(
            "materialize requires at least one Asset argument, e.x. `@materialize(asset1)`"
        )

    def decorator(fn: Callable[..., R]):
        task = MaterializationTask(fn, assets=assets, **task_kwargs)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            return task(*args, **kwargs)

        return wrapper

    return decorator
