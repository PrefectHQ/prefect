import asyncio
import signal
import sys
from functools import partial
from typing import Iterable, Optional

import anyio
import anyio.abc
import pendulum

from prefect import Task, get_client
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.schemas.objects import TaskRun
from prefect.client.subscriptions import Subscription
from prefect.logging.loggers import get_logger
from prefect.results import ResultFactory
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS,
)
from prefect.task_engine import submit_autonomous_task_to_engine
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.collections import distinct
from prefect.utilities.processutils import _register_signal

logger = get_logger("task_server")


class TaskServer:
    """This class is responsible for serving tasks that may be executed autonomously
    (i.e., without a parent flow run).

    When `start()` is called, the task server will subscribe to the task run scheduling
    topic and poll for scheduled task runs. When a scheduled task run is found, it
    will submit the task run to the engine for execution, using `submit_autonomous_task_to_engine`
    to construct a minimal `EngineContext` for the task run.

    Args:
        - tasks: A list of tasks to serve. These tasks will be submitted to the engine
            when a scheduled task run is found.
        - tags: A list of tags to apply to the task server. Defaults to `["autonomous"]`.
    """

    def __init__(
        self,
        *tasks: Task,
        tags: Optional[Iterable[str]] = None,
    ):
        self.tasks: list[Task] = tasks
        self.tags: Iterable[str] = tags or ["autonomous"]
        self.last_polled: Optional[pendulum.DateTime] = None
        self.started = False
        self.stopping = False

        self._client = get_client()

        if not asyncio.get_event_loop().is_running():
            raise RuntimeError(
                "TaskServer must be initialized within an async context."
            )

        self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

    def handle_sigterm(self, signum, frame):
        """
        Shuts down the task server when a SIGTERM is received.
        """
        logger.info("SIGTERM received, initiating graceful shutdown...")
        from_sync.call_in_loop_thread(create_call(self.stop))

        sys.exit(0)

    @sync_compatible
    async def start(self) -> None:
        """
        Starts a task server, which runs the tasks provided in the constructor.
        """
        _register_signal(signal.SIGTERM, self.handle_sigterm)

        async with asyncnullcontext() if self.started else self:
            await self._subscribe_to_task_scheduling()

    @sync_compatible
    async def stop(self):
        """Stops the task server's polling cycle."""
        if not self.started:
            raise RuntimeError(
                "Task server has not yet started. Please start the task server by"
                " calling .start()"
            )

        logger.info("Stopping task server...")
        self.started = False
        self.stopping = True

    async def _subscribe_to_task_scheduling(self):
        subscription = Subscription(TaskRun, "/task_runs/subscriptions/scheduled")
        logger.debug(f"Created: {subscription}")
        async for task_run in subscription:
            logger.info(f"Received task run: {task_run.id} - {task_run.name}")
            await self._submit_pending_task_run(task_run)

    async def _submit_pending_task_run(self, task_run: TaskRun):
        logger.debug(
            f"Found task run: {task_run.name!r} in state: {task_run.state.name!r}"
        )

        task = next((t for t in self.tasks if t.name in task_run.task_key), None)

        if not task:
            if PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS.value():
                logger.warning(
                    f"Task {task_run.name!r} not found in task server registry."
                )
                await self._client._client.delete(f"/task_runs/{task_run.id}")

            return

        # The ID of the parameters for this run are stored in the Scheduled state's
        # state_details. If there is no parameters_id, then the task was created
        # without parameters.
        parameters = {}
        if hasattr(task_run.state.state_details, "task_parameters_id"):
            parameters_id = task_run.state.state_details.task_parameters_id
            task.persist_result = True
            factory = await ResultFactory.from_task(task)
            try:
                parameters = await factory.read_parameters(parameters_id)
            except Exception as exc:
                logger.exception(
                    f"Failed to read parameters for task run {task_run.id!r}",
                    exc_info=exc,
                )
                if PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS.value():
                    logger.info(
                        f"Deleting task run {task_run.id!r} because it failed to submit"
                    )
                    await self._client._client.delete(f"/task_runs/{task_run.id}")
                return

        logger.debug(
            f"Submitting run {task_run.name!r} of task {task.name!r} to engine"
        )

        task_run.tags = distinct(task_run.tags + list(self.tags))

        self._runs_task_group.start_soon(
            partial(
                submit_autonomous_task_to_engine,
                task=task,
                task_run=task_run,
                parameters=parameters,
            )
        )

    async def __aenter__(self):
        logger.debug("Starting task server...")
        self._client = get_client()
        await self._client.__aenter__()
        await self._runs_task_group.__aenter__()

        self.started = True
        return self

    async def __aexit__(self, *exc_info):
        logger.debug("Stopping task server...")
        self.started = False
        if self._runs_task_group:
            await self._runs_task_group.__aexit__(*exc_info)
        if self._client:
            await self._client.__aexit__(*exc_info)


@sync_compatible
async def serve(*tasks: Task, tags: Optional[Iterable[str]] = None):
    """Serve the provided tasks so that they may be executed autonomously.

    Args:
        - tasks: A list of tasks to serve. When a scheduled task run is found for a
            given task, the task run will be submitted to the engine for execution.
        - tags: A list of tags to apply to the task server. Defaults to `["autonomous"]`.

    Example:
        ```python
        from prefect import task
        from prefect.task_server import serve

        @task(log_prints=True)
        def say(message: str):
            print(message)

        @task(log_prints=True)
        def yell(message: str):
            print(message.upper())

        # starts a long-lived process that listens scheduled runs of these tasks
        if __name__ == "__main__":
            serve(say, yell)
        ```
    """
    if not PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING.value():
        raise RuntimeError(
            "To enable task scheduling, set PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING"
            " to True."
        )

    task_server = TaskServer(*tasks, tags=tags)
    await task_server.start()
