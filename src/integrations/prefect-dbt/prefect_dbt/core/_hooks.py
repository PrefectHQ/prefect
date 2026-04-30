from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, TypeAlias, TypeVar, overload

from dbt.contracts.graph.nodes import ManifestNode, SourceDefinition

from prefect.logging import get_logger
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect_dbt.core._manifest import DbtNode, resolve_selection

DbtHookEvent: TypeAlias = Literal["run_start", "run_end", "post_model"]
DbtHookNode: TypeAlias = DbtNode | ManifestNode | SourceDefinition
DbtHookCallable: TypeAlias = Callable[["DbtHookContext"], Any]

F = TypeVar("F", bound=DbtHookCallable)
DbtHookDecorator: TypeAlias = Callable[[DbtHookCallable], DbtHookCallable]

logger = get_logger(__name__)


@dataclass(frozen=True)
class DbtHookContext:
    event: DbtHookEvent
    command: str
    owner: Any
    args: tuple[str, ...] = ()
    node: DbtHookNode | None = None
    status: str | None = None
    result: dict[str, Any] | None = None
    run_results: dict[str, Any] | None = None
    error: Any = None
    node_ids: tuple[str, ...] = ()

    @property
    def node_id(self) -> str | None:
        return getattr(self.node, "unique_id", None)


@dataclass(frozen=True)
class _RegisteredDbtHook:
    callback: DbtHookCallable
    select: str | None = None


class DbtHookMixin:
    def _initialize_dbt_hooks(self) -> None:
        self._dbt_hooks: dict[DbtHookEvent, list[_RegisteredDbtHook]] = {
            "run_start": [],
            "run_end": [],
            "post_model": [],
        }

    def _register_dbt_hook(
        self,
        event: DbtHookEvent,
        fn: DbtHookCallable | None = None,
        *,
        select: str | None = None,
    ) -> DbtHookCallable | Callable[[DbtHookCallable], DbtHookCallable]:
        def decorator(callback: DbtHookCallable) -> DbtHookCallable:
            self._dbt_hooks[event].append(
                _RegisteredDbtHook(callback=callback, select=select)
            )
            return callback

        if fn is None:
            return decorator

        return decorator(fn)

    @overload
    def on_run_start(self, fn: F) -> F: ...

    @overload
    def on_run_start(self) -> DbtHookDecorator: ...

    def on_run_start(
        self,
        fn: DbtHookCallable | None = None,
    ) -> DbtHookCallable | DbtHookDecorator:
        return self._register_dbt_hook("run_start", fn)

    @overload
    def on_run_end(self, fn: F) -> F: ...

    @overload
    def on_run_end(self, *, select: str | None = ...) -> DbtHookDecorator: ...

    def on_run_end(
        self,
        fn: DbtHookCallable | None = None,
        *,
        select: str | None = None,
    ) -> DbtHookCallable | DbtHookDecorator:
        return self._register_dbt_hook("run_end", fn, select=select)

    @overload
    def post_model(self, fn: F) -> F: ...

    @overload
    def post_model(self, *, select: str | None = ...) -> DbtHookDecorator: ...

    def post_model(
        self,
        fn: DbtHookCallable | None = None,
        *,
        select: str | None = None,
    ) -> DbtHookCallable | DbtHookDecorator:
        return self._register_dbt_hook("post_model", fn, select=select)

    def _has_dbt_hooks(self) -> bool:
        return any(self._dbt_hooks.values())

    def _build_dbt_hook_selection_cache(
        self,
        *,
        project_dir: Path,
        profiles_dir: Path,
        target_path: Path | None = None,
        target: str | None = None,
    ) -> dict[str, set[str]]:
        cache: dict[str, set[str]] = {}
        for hooks in self._dbt_hooks.values():
            for hook in hooks:
                if hook.select is None or hook.select in cache:
                    continue
                try:
                    cache[hook.select] = resolve_selection(
                        project_dir=project_dir,
                        profiles_dir=profiles_dir,
                        select=hook.select,
                        target_path=target_path,
                        target=target,
                    )
                except Exception:
                    logger.warning(
                        "Failed to resolve dbt hook selector %r; skipping matching hooks.",
                        hook.select,
                        exc_info=True,
                    )
                    cache[hook.select] = set()
        return cache

    def _dbt_hook_matches(
        self,
        hook: _RegisteredDbtHook,
        context: DbtHookContext,
        selection_cache: dict[str, set[str]],
    ) -> bool:
        if hook.select is None:
            return True

        selected_node_ids = selection_cache.get(hook.select, set())
        if context.node_id is not None:
            return context.node_id in selected_node_ids
        if context.node_ids:
            return any(node_id in selected_node_ids for node_id in context.node_ids)
        return bool(selected_node_ids)

    def _run_dbt_hooks(
        self,
        event: DbtHookEvent,
        context: DbtHookContext,
        *,
        selection_cache: dict[str, set[str]] | None = None,
    ) -> None:
        cache = selection_cache or {}
        for hook in self._dbt_hooks[event]:
            if not self._dbt_hook_matches(hook, context, cache):
                continue
            try:
                hook_result = hook.callback(context)
                if inspect.isawaitable(hook_result):
                    run_coro_as_sync(hook_result)
            except Exception:
                logger.warning(
                    "dbt hook %s failed during %s.",
                    getattr(hook.callback, "__name__", repr(hook.callback)),
                    event,
                    exc_info=True,
                )
