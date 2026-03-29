"""
Task queue backend protocol and loader for delivering background task runs
to TaskWorkers.

Protocol:
    TaskQueueBackend — single instance manages all keys with a multi-key
    (dequeue_from_keys) read path.

The default in-memory backend is at prefect.server.task_queue.memory.
"""

import importlib
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import prefect.server.schemas as schemas
from prefect.settings import get_current_settings


@dataclass
class DeliveredTaskRun:
    """Wrapper returned by dequeue_from_keys.

    Carries an opaque ack_token that the caller passes back to ack()
    without inspecting. Backend-specific: None for memory, dict for
    Redis Streams, integer for RabbitMQ, etc.
    """

    task_run: schemas.core.TaskRun
    ack_token: Any = None


@runtime_checkable
class TaskQueueModule(Protocol):
    TaskQueueBackend: type["TaskQueueBackend"]


class TaskQueueBackend(Protocol):
    """Protocol for a task queue backend.

    A single instance manages all keys. Write methods (enqueue, retry) extract
    the key from task_run.task_key. Read methods accept explicit keys.
    """

    async def enqueue(self, task_run: schemas.core.TaskRun) -> None:
        """Route a task run to the scheduled queue for its task_key."""
        ...

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        """Route a task run to the retry (priority) queue for its task_key."""
        ...

    async def ack(self, delivered: DeliveredTaskRun) -> None:
        """Acknowledge successful delivery of a task run.

        Implementations that track in-flight state should clean up here.
        """
        ...

    async def dequeue_from_keys(
        self,
        keys: list[str],
        timeout: float = 1,
    ) -> DeliveredTaskRun:
        """Dequeue the next available task run from any of the given keys.

        Per key, retries are checked before scheduled items. The
        implementation is responsible for fair scheduling across keys.
        Raises asyncio.TimeoutError if nothing available within timeout.
        """
        ...


def get_task_queue_backend() -> TaskQueueBackend:
    """Return a TaskQueueBackend instance for the configured backend.

    Loads the backend module from the PREFECT_TASK_SCHEDULING_BACKEND setting
    and validates that it exports a TaskQueueBackend class.

    Backend classes use the singleton pattern (`__new__` + `_instance`),
    so repeated calls return the same instance.
    """
    module_path = get_current_settings().server.tasks.scheduling.backend
    module = importlib.import_module(module_path)
    if not isinstance(module, TaskQueueModule):
        raise ValueError(
            f"Module at {module_path} does not export a TaskQueueBackend class. "
            "Check your PREFECT_TASK_SCHEDULING_BACKEND setting."
        )
    return module.TaskQueueBackend()
