from __future__ import annotations

from collections import defaultdict
from functools import wraps
from typing import Callable, DefaultDict, Generic, List, Sequence, Set, TypeVar
from uuid import UUID

from prefect import Task
from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import TaskRun
from prefect.context import FlowRunContext
from prefect.events import emit_event
from prefect.states import State
from prefect.types._datetime import now

T = TypeVar("T")
P = TypeVar("P")
R = TypeVar("R")


class Asset:
    def __init__(
        self,
        *,
        key: str,
        name: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        self.key = key
        self.name = name or key
        self.metadata = metadata or {}

    def as_resource(self) -> dict[str, str]:
        d = {
            "prefect.resource.id": self.key,
            "prefect.resource.name": self.name,
        }
        d.update(self.metadata)
        return d

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


def _asset_cache(ctx: FlowRunContext) -> dict[UUID, list[Asset]]:
    if not hasattr(ctx, "_task_run_assets"):
        ctx._task_run_assets = {}
    return ctx._task_run_assets  # type: ignore[attr-defined]


def _parents_table(ctx: FlowRunContext) -> DefaultDict[UUID, Set[UUID]]:
    if not hasattr(ctx, "_task_run_parents"):
        ctx._task_run_parents = defaultdict(set)

    return ctx._task_run_parents  # type: ignore[attr-defined]


class MaterializationTask(Task, Generic[P, R]):
    def __init__(self, fn: Callable[..., R], *, assets: Sequence[Asset], **task_kwargs):
        self.assets: list[Asset] = list(assets)

        on_completion = task_kwargs.pop("on_completion", [])
        on_fail = task_kwargs.pop("on_failure", [])
        task_kwargs["on_completion"] = [self._hook_success, *on_completion]
        task_kwargs["on_failure"] = [self._hook_failure, *on_fail]
        super().__init__(fn=fn, **task_kwargs)

    def _hook_success(self, task, task_run: TaskRun, state: State):
        self._record_assets(task_run)
        self._emit_events(task_run, succeeded=True)

    def _hook_failure(self, task, task_run: TaskRun, state: State):
        self._record_assets(task_run)
        self._emit_events(task_run, succeeded=False)

    def _record_assets(self, task_run: TaskRun) -> None:
        ctx = FlowRunContext.get()
        if not ctx:
            return
        _asset_cache(ctx)[task_run.id] = self.assets

    def _discover_upstream_assets(self, task_run: TaskRun) -> list[Asset]:
        ctx = FlowRunContext.get()
        if not ctx:
            return []

        parents_tbl = _parents_table(ctx)
        assets_tbl = _asset_cache(ctx)

        todo: List[UUID] = list(parents_tbl.get(task_run.id, ()))
        seen: Set[UUID] = set()
        found: list[Asset] = []

        while todo:
            rid = todo.pop()
            if rid in seen:
                continue
            seen.add(rid)

            for a in assets_tbl.get(rid, ()):
                if a not in found:
                    found.append(a)

            todo.extend(parents_tbl.get(rid, ()))

        return found

    def _emit_events(self, task_run: TaskRun, *, succeeded: bool) -> None:
        ctx = FlowRunContext.get()
        if not ctx:
            return

        runtime_related = [
            {
                "prefect.resource.id": f"prefect.flow-run.{ctx.flow_run.id}",
                "prefect.resource.role": "flow-run",
            },
            {
                "prefect.resource.id": f"prefect.task-run.{task_run.id}",
                "prefect.resource.role": "task-run",
            },
        ]

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
            related = related + runtime_related

            emit_event(
                id=uuid7(),
                occurred=now(),
                event=event,
                resource=asset.as_resource(),
                related=related,
                payload={},
            )


def materialize(*assets: Asset, **task_kwargs):
    if not assets:
        raise TypeError("materialize() requires at least one Asset")

    def decorator(fn: Callable[..., R]):
        task = MaterializationTask(fn, assets=assets, **task_kwargs)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            return task(*args, **kwargs)

        return wrapper

    return decorator
