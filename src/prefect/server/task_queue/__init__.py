"""
Task queue backend protocol and loader for delivering background task runs
to TaskWorkers.

Protocol:
    TaskQueueBackend — single instance manages all keys with both blocking
    (get) and multi-key (get_many) read paths.

The default in-memory backend is at prefect.server.task_queue.memory.
"""

import importlib
from typing import Protocol, runtime_checkable

import prefect.server.schemas as schemas
from prefect.settings import get_current_settings


@runtime_checkable
class TaskQueueModule(Protocol):
    TaskQueueBackend: type["TaskQueueBackend"]


class TaskQueueBackend(Protocol):
    """Protocol for a task queue backend.

    A single instance manages all keys. Write methods (enqueue, retry) extract
    the key from task_run.task_key. Read methods accept explicit keys.

    Backpressure contract: enqueue() and retry() block until capacity is
    available. Backends must not silently drop items or allow unbounded growth
    beyond their configured limits.
    """

    async def enqueue(self, task_run: schemas.core.TaskRun) -> None:
        """Route a task run to the scheduled queue for its task_key."""
        ...

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        """Route a task run to the retry (priority) queue for its task_key."""
        ...

    async def get(self, key: str) -> schemas.core.TaskRun:
        """Block until a task run is available for the given key.
        Retry queue has priority over scheduled queue."""
        ...

    async def get_many(
        self,
        keys: list[str],
        timeout: float = 1,
        offset: int = 0,
    ) -> schemas.core.TaskRun:
        """Get the next available task from any of the given keys.

        Per key in rotated order, retries are checked before scheduled items.
        Raises asyncio.TimeoutError if nothing available within timeout.
        offset enables round-robin rotation across calls.
        """
        ...

    @staticmethod
    def prioritize_keys(task_keys: list[str], offset: int) -> list[str]:
        """Return task_keys in the order they should be checked.
        offset increments per call, enabling round-robin rotation, among other options."""
        ...


def get_task_queue_backend() -> TaskQueueBackend:
    """Return a TaskQueueBackend instance for the configured backend.

    Loads the backend module from the PREFECT_TASK_SCHEDULING_BACKEND setting
    and validates that it exports a TaskQueueBackend class.
    """
    module_path = get_current_settings().server.tasks.scheduling.backend
    module = importlib.import_module(module_path)
    if not isinstance(module, TaskQueueModule):
        raise ValueError(
            f"Module at {module_path} does not export a TaskQueueBackend class. "
            "Check your PREFECT_TASK_SCHEDULING_BACKEND setting."
        )
    return module.TaskQueueBackend()
