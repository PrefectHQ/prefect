from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.server.api import (
        admin,
        artifacts,
        automations,
        block_capabilities,
        block_documents,
        block_schemas,
        block_types,
        collections,
        concurrency_limits,
        concurrency_limits_v2,
        csrf_token,
        dependencies,
        deployments,
        events,
        flow_run_states,
        flow_runs,
        flows,
        logs,
        middleware,
        root,
        run_history,
        saved_searches,
        server,
        task_run_states,
        task_runs,
        task_workers,
        templates,
        ui,
        variables,
        work_queues,
        workers,
    )

__all__ = [
    "admin",
    "artifacts",
    "automations",
    "block_capabilities",
    "block_documents",
    "block_schemas",
    "block_types",
    "collections",
    "concurrency_limits",
    "concurrency_limits_v2",
    "csrf_token",
    "dependencies",
    "deployments",
    "events",
    "flow_run_states",
    "flow_runs",
    "flows",
    "logs",
    "middleware",
    "root",
    "run_history",
    "saved_searches",
    "server",
    "task_run_states",
    "task_runs",
    "task_workers",
    "templates",
    "ui",
    "variables",
    "work_queues",
    "workers",
]


def __getattr__(name: str) -> object:
    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    globals()[name] = module
    return module
